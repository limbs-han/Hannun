"""silver 창을 DS 입력 JSONL 로 내려준다 (DS 연동).

DS 파이프라인(hannun-ingest)은 로컬 파일만 읽고 형식은 .json/.jsonl/.ndjson 만
받는다. silver 는 HDFS parquet 이라 그대로는 읽을 수 없어, 날짜별로 한 파일씩
로컬에 풀어준다. DS 코드는 손대지 않는다.

  <out>/YYYY/YYYY-MM-DD.jsonl   (비압축, 한 줄에 기사 하나, 하루는 항상 파일 하나)

파일명이 .jsonl 이어야 한다 — DS 의 reader 는 .json 을 한 덩어리 JSON 으로 읽어서
확장자가 .json 이면 파싱이 깨진다. 그래서 Spark 쓰기 대신 드라이버에서 직접 쓴다.
하루치가 기사 몇천 건이라 이 방식으로 충분하고, 파일 이름과 개수를 정확히 맞출 수 있다.

같은 날짜를 다시 내려도 안전하다. 지난 날짜 파티션에도 기사가 뒤늦게 추가되므로
(RSS 가 며칠 전 기사를 준다) 최근 며칠을 다시 내리는 것을 전제로 만들었다.

  spark-submit --master local[*] jobs/silver_to_ds_input.py               # 어제(KST) 하루
  spark-submit --master local[*] jobs/silver_to_ds_input.py --recent 3    # 어제부터 3일
  spark-submit --master local[*] jobs/silver_to_ds_input.py 2026-09-01 2026-09-07
  spark-submit --master local[*] jobs/silver_to_ds_input.py --sync         # 뒤처진 날짜만
  spark-submit --master local[*] jobs/silver_to_ds_input.py --bulk         # silver 전체
  spark-submit --master local[*] jobs/silver_to_ds_input.py --bulk 2019-01-01 2019-12-31
"""

import argparse
import datetime as dt
import json
import logging
import os
import shutil

from pyspark.sql import SparkSession
from pyspark.sql.functions import col
from pyspark.sql.utils import AnalysisException

logger = logging.getLogger("silver_to_ds_input")

LAKE = os.environ.get("LAKE_ROOT", "hdfs://namenode:8020/lake")
SILVER = f"{LAKE}/silver/news"
OUT_ROOT = os.environ.get("DS_INPUT_ROOT", "/opt/airflow/ds_input")
KST = dt.timezone(dt.timedelta(hours=9))

# dt 는 파티션 이름일 뿐이라 기사 레코드에는 넣지 않는다. DS 계약(article_v1)에 없는 필드다
PARTITION_COLUMN = "dt"


def yesterday_kst(now=None):
    """어제의 한국 날짜. dt 파티션이 한국 날짜 기준이라 UTC 로 계산하면 하루 밀린다."""
    now = now or dt.datetime.now(dt.timezone.utc)
    return str(now.astimezone(KST).date() - dt.timedelta(days=1))


def date_range(start, end):
    first, last = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
    if last < first:
        raise ValueError(f"끝 날짜가 시작보다 앞선다: {start} ~ {end}")
    return [str(first + dt.timedelta(days=n)) for n in range((last - first).days + 1)]


def target_days(dates, recent, now=None):
    """내려줄 날짜 목록. 인자가 없으면 어제부터 recent 일을 거슬러 잡는다."""
    if len(dates) == 2:
        return date_range(dates[0], dates[1])
    if len(dates) == 1:
        return [dates[0]]
    last = dt.date.fromisoformat(yesterday_kst(now))
    return date_range(str(last - dt.timedelta(days=recent - 1)), str(last))


def to_json_line(row):
    """행 하나를 DS 가 읽는 JSON 한 줄로. 파티션 컬럼은 제외한다."""
    record = {k: v for k, v in row.asDict().items() if k != PARTITION_COLUMN}
    return json.dumps(record, ensure_ascii=False)


def day_file(out_root, day):
    """DS 가 읽는 하루 파일. 연도로 묶고 날짜를 파일명으로 쓴다.

    하루에 폴더를 두지 않는 이유는 파일이 하나뿐이라 폴더가 아무 역할을 하지 않고,
    연도 폴더에서 날짜와 크기를 한눈에 보기 어려워지기 때문이다. lake 와 달리 dt=
    접두어도 붙이지 않는다. DS 는 Spark 가 아니라 파일 경로로 읽어 접두어가 쓸모없다.
    하루가 항상 파일 하나라는 약속을 지키므로 읽는 쪽은 이 경로만 알면 된다."""
    return os.path.join(out_root, day[:4], f"{day}.jsonl")


def staging_path(final):
    """쓰는 중인 파일 경로. 프로세스마다 달라야 한다 — 같은 날짜를 두 프로세스가
    동시에 내리면 고정 이름이면 서로의 내용이 섞인다."""
    return f"{final}.tmp.{os.getpid()}"


def export_day(spark, day, out_root):
    """하루치를 <out_root>/<연도>/<날짜>.jsonl 로 쓴다. 파티션이 없으면 None."""
    try:
        rows = spark.read.parquet(f"{SILVER}/dt={day}")
    except AnalysisException:
        logger.info("silver 에 없는 날짜, 건너뜀: %s", day)
        return None

    final = day_file(out_root, day)
    os.makedirs(os.path.dirname(final), exist_ok=True)
    staging = staging_path(final)

    count = 0
    # toLocalIterator: 하루치를 드라이버 메모리에 한꺼번에 올리지 않고 흘려 쓴다
    with open(staging, "w", encoding="utf-8") as out:
        for row in rows.toLocalIterator():
            out.write(to_json_line(row) + "\n")
            count += 1
    # 다 쓴 뒤 제자리로 옮긴다 — DS 가 쓰는 중인 파일을 읽는 일을 막는다
    os.replace(staging, final)  # 같은 파일시스템이라 원자적이다
    logger.info("내려주기 완료 %s: %s건 → %s", day, f"{count:,}", final)
    return count


def normalize_staging(staging, out_root):
    """Spark 가 쓴 dt=<날짜>/part-*.json 을 DS 가 읽는 이름과 자리로 옮긴다.

    Spark 쓰기는 파일명을 정할 수 없어 확장자가 .json 으로 나온다. DS 는 .json 을 한
    덩어리 JSON 으로 읽어 그대로 두면 파싱이 깨진다.

    하루가 여러 조각으로 나뉘면 이어붙여 파일 하나로 만든다. 하루가 항상 파일 하나여야
    읽는 쪽이 그 경로만 알면 되고, 조각 하나만 가리켜 나머지를 조용히 빼먹는 일이 없다.
    쪼개지는 것은 하루가 Spark 의 분할 기준(128MB)을 넘을 때뿐이라 비용은 거의 안 든다.
    """
    days = 0
    for name in sorted(os.listdir(staging)):
        if not name.startswith("dt="):
            continue  # _SUCCESS 등
        day = name[len("dt="):]
        source = os.path.join(staging, name)
        final = day_file(out_root, day)
        os.makedirs(os.path.dirname(final), exist_ok=True)
        parts = sorted(os.path.join(source, f) for f in os.listdir(source) if f.startswith("part-"))
        if len(parts) == 1:
            os.replace(parts[0], final)  # 같은 파일시스템이라 옮기기는 즉시다
        else:
            logger.info("%s 는 %d조각 — 이어붙임", day, len(parts))
            with open(parts[0], "ab") as first:
                for extra in parts[1:]:
                    with open(extra, "rb") as chunk:
                        shutil.copyfileobj(chunk, first)
                    os.remove(extra)
            os.replace(parts[0], final)
        days += 1
    shutil.rmtree(staging, ignore_errors=True)
    return days


def silver_partition_mtimes(spark):
    """silver 날짜 파티션의 마지막 변경 시각. {날짜: 초 단위 시각}.

    파티션을 덮어쓸 때 폴더 안 파일이 바뀌므로 폴더의 변경 시각이 함께 갱신된다.
    파티션마다 안을 들여다보지 않고 한 번의 목록 조회로 끝내려고 폴더 시각을 쓴다.
    """
    jvm = spark.sparkContext._jvm
    conf = spark.sparkContext._jsc.hadoopConfiguration()
    fs = jvm.org.apache.hadoop.fs.FileSystem.get(jvm.java.net.URI(LAKE), conf)
    prefix = f"{PARTITION_COLUMN}="
    mtimes = {}
    for status in fs.listStatus(jvm.org.apache.hadoop.fs.Path(SILVER)):
        name = status.getPath().getName()
        if name.startswith(prefix):
            mtimes[name[len(prefix):]] = status.getModificationTime() / 1000.0
    return mtimes


def stale_days(partition_mtimes, out_root):
    """내려준 파일이 silver 보다 뒤처진 날짜. 파일이 없으면 당연히 대상이다.

    고정된 최근 며칠이 아니라 실제로 바뀐 날짜를 고른다. RSS 가 몇 달 전 기사를 뒤늦게
    주면 그 옛 날짜의 silver 가 갱신되는데(2026-06-09 실측), 최근 며칠만 내리면 그 기사는
    DS 에게 영구히 가지 않는다.
    """
    stale = []
    for day, mtime in partition_mtimes.items():
        path = day_file(out_root, day)
        if not os.path.exists(path) or os.path.getmtime(path) < mtime:
            stale.append(day)
    return sorted(stale)


def export_bulk(spark, out_root, days=None, start=None, end=None):
    """지정한 날짜들을 한 번에 읽어 날짜별로 쓴다. 아무것도 안 주면 silver 전부.

    날짜마다 따로 읽는 export_day 는 준비 비용이 커서 하루에 1분씩 걸린다. 2,800일이면
    이틀이 넘어 15분 파이프라인이 그만큼 멈춘다. 한 번에 읽으면 7분이다(실측).
    """
    df = spark.read.parquet(SILVER)
    if days is not None:
        df = df.where(col(PARTITION_COLUMN).isin(days))
    elif start and end:
        df = df.where((col(PARTITION_COLUMN) >= start) & (col(PARTITION_COLUMN) <= end))
    staging = os.path.join(out_root, "_staging")
    shutil.rmtree(staging, ignore_errors=True)
    (df.write.mode("overwrite")
     # 기본값은 null 필드를 아예 빼버린다. 날짜별 내려주기와 같은 모양을 유지하려면 꺼야 한다
     .option("ignoreNullFields", "false")
     # 파티션 컬럼은 폴더 이름으로만 남고 파일 내용에서 빠진다 — article_v1 에 없는 필드다
     .partitionBy(PARTITION_COLUMN)
     .json(f"file://{staging}"))
    written = normalize_staging(staging, out_root)
    logger.info("내려주기 완료: %d일", written)
    return written


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("dates", nargs="*", metavar="날짜", help="시작일 [끝일]. 생략하면 --recent 범위")
    ap.add_argument("--recent", type=int, default=1, help="어제부터 거슬러 며칠 (기본 1)")
    ap.add_argument("--bulk", action="store_true",
                    help="구간을 한 번에 읽어 내린다. 날짜를 생략하면 silver 전체")
    ap.add_argument("--sync", action="store_true",
                    help="내려준 파일이 silver 보다 뒤처진 날짜만 골라 내린다 (매일 실행용)")
    args = ap.parse_args()

    spark = (
        SparkSession.builder.appName("silver_to_ds_input")
        .config("spark.locality.wait", "0")  # bronze_to_silver 와 같은 이유 (local 모드 교착)
        .getOrCreate()
    )
    try:
        if args.sync:
            stale = stale_days(silver_partition_mtimes(spark), OUT_ROOT)
            if stale:
                logger.info("뒤처진 날짜 %d일: %s%s", len(stale), stale[:5],
                            " ..." if len(stale) > 5 else "")
                export_bulk(spark, OUT_ROOT, days=stale)
            else:
                logger.info("뒤처진 날짜 없음")
        elif args.bulk:
            start, end = (args.dates + [None, None])[:2]
            export_bulk(spark, OUT_ROOT, start=start, end=end)
        else:
            days = target_days(args.dates, args.recent)
            total = {day: export_day(spark, day, OUT_ROOT) for day in days}
            written = {d: n for d, n in total.items() if n is not None}
            logger.info("총 %d일, %s건", len(written), f"{sum(written.values()):,}")
    finally:
        spark.stop()
