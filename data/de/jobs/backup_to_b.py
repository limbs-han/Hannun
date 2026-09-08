"""bronze/news 하루 파티션과 수집기 상태를 B 서버로 백업한다 (S15P21E105-74).

지키는 대상은 잃으면 되돌릴 수 없는 것뿐이다. Kafka 보관은 7일이라 그 뒤에는 실시간
기사를 다시 받을 길이 없고, seen.sqlite 를 잃으면 지난 기사를 다시 발행한다. 데이터셋
CSV(로컬에 원본 있음)와 silver(재구축 가능)는 백업하지 않는다.

HDFS 는 WebHDFS 로 읽는다. hdfs 명령은 namenode 컨테이너에만 있고 ssh·rsync 는 airflow
컨테이너에만 있어서, 한 컨테이너에서 둘 다 되는 유일한 방법이다. 받은 내용은 흐름으로
바로 압축해 A 디스크에 원본 사본을 남기지 않는다.

  python jobs/backup_to_b.py [YYYY-MM-DD]
"""

import datetime as dt
import gzip
import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request

logger = logging.getLogger("backup_to_b")

WEBHDFS = os.environ.get("WEBHDFS", "http://namenode:9870/webhdfs/v1")
PARTITION = "/lake/bronze/news/ingest_date={day}"
KEY = os.environ.get("B_SSH_KEY", "/opt/airflow/.ssh/b.pem")
HOST = os.environ.get("B_HOST", "ubuntu@j15e105.p.ssafy.io")
DEST = os.environ.get("B_BACKUP_DIR", "/home/ubuntu/backup/de")
KEEP_DAYS = int(os.environ.get("BACKUP_KEEP_DAYS", "30"))
BWLIMIT = os.environ.get("BACKUP_BWLIMIT", "20000")  # KB/s, 서비스 트래픽과 겹치지 않게
SEEN_DB = os.environ.get("SEEN_DB", "/opt/airflow/state/seen.sqlite")
SSH = f"ssh -i {KEY} -o StrictHostKeyChecking=accept-new -o BatchMode=yes"


def _open(url):
    return urllib.request.urlopen(url, timeout=60)


def list_parts(day, opener=_open):
    """파티션의 part 파일 이름을 정렬해 돌려준다. 파티션이 없으면 None."""
    url = f"{WEBHDFS}{urllib.parse.quote(PARTITION.format(day=day))}?op=LISTSTATUS"
    try:
        with opener(url) as response:
            listing = json.load(response)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise
    return sorted(
        item["pathSuffix"]
        for item in listing["FileStatuses"]["FileStatus"]
        if item["pathSuffix"].startswith("part-")
    )


def archive_parts(day, parts, out_path, opener=_open):
    """part 파일들을 흐름으로 받아 gzip 하나로 합치고 줄 수를 돌려준다."""
    lines = 0
    with gzip.open(out_path, "wb") as out:
        for name in parts:
            path = urllib.parse.quote(f"{PARTITION.format(day=day)}/{name}")
            with opener(f"{WEBHDFS}{path}?op=OPEN") as response:
                while chunk := response.read(1 << 20):
                    lines += chunk.count(b"\n")
                    out.write(chunk)
    return lines


def _run(command, **kwargs):
    return subprocess.run(command, shell=True, check=True, text=True, **kwargs)


def backup(day):
    parts = list_parts(day)
    if not parts:
        logger.info("백업할 파티션 없음: %s", day)
        return None

    work = tempfile.mkdtemp()
    try:
        archive = os.path.join(work, f"news_{day}.tar.gz")
        lines = archive_parts(day, parts, archive)
        if lines == 0:
            raise RuntimeError(f"받은 줄이 0 — 백업 중단: {day}")

        # sqlite 는 복사 중 바뀔 수 있어 .backup 으로 일관된 사본을 뜬다
        if os.path.exists(SEEN_DB):
            _run(f"sqlite3 {SEEN_DB} \".backup '{work}/seen.sqlite'\"")
            with open(f"{work}/seen.sqlite", "rb") as raw, gzip.open(f"{work}/seen.sqlite.gz", "wb") as gz:
                shutil.copyfileobj(raw, gz)
            os.remove(f"{work}/seen.sqlite")

        with open(os.path.join(work, "SHA256SUMS"), "w") as sums:
            for name in sorted(os.listdir(work)):
                if name == "SHA256SUMS":
                    continue
                digest = hashlib.sha256(open(os.path.join(work, name), "rb").read()).hexdigest()
                sums.write(f"{digest}  {name}\n")

        _run(f"{SSH} {HOST} 'mkdir -p {DEST}/{day}'")
        _run(f"rsync -a --bwlimit={BWLIMIT} -e '{SSH}' {work}/ {HOST}:{DEST}/{day}/")
        # 검증은 받은 쪽에서 한다 — 보낸 파일이 아니라 도착한 파일이 온전한지가 중요하다
        _run(f"{SSH} {HOST} 'cd {DEST}/{day} && sha256sum -c SHA256SUMS --quiet'")
        # 보관 기간 초과 삭제. 날짜 형식 폴더만 지운다
        _run(f"{SSH} {HOST} \"find {DEST} -maxdepth 1 -type d -name '20*-*-*' -mtime +{KEEP_DAYS} "
             f"-exec rm -rf {{}} +\"")

        size = sum(os.path.getsize(os.path.join(work, f)) for f in os.listdir(work))
        logger.info("백업 완료 %s: 파일 %d개, %s줄, %.1fMB → %s:%s/%s (보관 %d일)",
                    day, len(parts), f"{lines:,}", size / 1e6, HOST, DEST, day, KEEP_DAYS)
        return lines
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    target = sys.argv[1] if len(sys.argv) > 1 else str(dt.date.today() - dt.timedelta(days=1))
    backup(target)
