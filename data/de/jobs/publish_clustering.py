"""gold 이슈 피드를 BE 로 발행한다 (S15P21E105-69).

토픽 news.clustering.completed, 이슈 하나가 메시지 하나, key 는 clusterId 문자열이다.
매번 전체를 보낸다(BE 협의). 같은 key 로 다시 가므로 BE 가 갱신으로 처리한다.

관점 라벨과 성향, 요약은 DS 코드가 아직 없어 gold 에 비어 있다. BE 가 필수로 요구하므로
--mock-viewpoints 를 줄 때만 목업으로 채운다. 옵션 없이 돌리면 빈 값이 그대로 나가
BE 검증에 걸린다. 목업을 실수로 보내지 않게 하려는 것이다.

  python jobs/publish_clustering.py 2026-09-08 --dry-run
  python jobs/publish_clustering.py 2026-09-08 --mock-viewpoints --dry-run
  KAFKA_BROKER=... python jobs/publish_clustering.py 2026-09-08 --mock-viewpoints --send
"""

import argparse
import datetime as dt
import json
import logging
import os
import time

logger = logging.getLogger("publish_clustering")

TOPIC = os.environ.get("CLUSTERING_TOPIC", "news.clustering.completed")
BROKER = os.environ.get("KAFKA_BROKER", "")
RATE_PER_SEC = float(os.environ.get("PUBLISH_RATE_PER_SEC", "50"))
WEBHDFS = os.environ.get("WEBHDFS", "http://namenode:9870/webhdfs/v1")
GOLD_PATH = os.environ.get("GOLD_PATH", "/lake/gold/issue_feed")
KST = dt.timezone(dt.timedelta(hours=9))

# BE 예시 문구를 본뜬 관점 이름. 그룹마다 성향을 하나로 고정해 실제 서비스 모양을 흉내낸다
MOCK_VIEWPOINTS = [
    ("경제적 기대 효과", "positive"), ("사회적 형평성", "negative"),
    ("절차와 투명성", "neutral"), ("산업 경쟁력", "positive"),
    ("재정 부담", "negative"), ("현장 수용성", "neutral"),
    ("국제 비교", "neutral"), ("당사자 권리", "negative"),
]


def to_kst_iso(value):
    """ISO-8601 + 한국 오프셋. BE 가 오프셋 있는 형식을 요구한다."""
    if isinstance(value, str):
        value = dt.datetime.fromisoformat(value)
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.timezone.utc)
    return value.astimezone(KST).isoformat(timespec="seconds")


def mock_groups(cluster_id, member_count):
    """이슈 하나에 붙일 관점 그룹. 기사가 적으면 2개, 많으면 3개."""
    count = 2 if member_count < 6 else 3
    start = cluster_id % len(MOCK_VIEWPOINTS)
    picked = [MOCK_VIEWPOINTS[(start + i) % len(MOCK_VIEWPOINTS)] for i in range(count)]
    return [(f"[샘플] A-{i + 1} {name}", stance) for i, (name, stance) in enumerate(picked)]


def missing_required(message):
    """BE 필수 필드 중 빈 것을 돌려준다. 목업 없이 보낼 수 있는지 미리 보는 데 쓴다."""
    missing = [k for k in ("clusterId", "category", "factSummary",
                           "commonFactsBriefing", "clusteredAt")
               if message.get(k) in (None, "")]
    for article in message["articles"]:
        for key in ("link", "viewpointGroupLabel", "stance"):
            if article.get(key) in (None, "") and f"articles[].{key}" not in missing:
                missing.append(f"articles[].{key}")
    return missing


def build_message(rows, mock=False):
    """한 이슈의 행들을 BE 스펙 메시지로 조립한다. rows 는 같은 cluster_id 의 행들."""
    rows = sorted(rows, key=lambda r: r["published_at"])
    head = rows[0]
    groups = mock_groups(head["cluster_id"], len(rows)) if mock else None
    articles = []
    for i, r in enumerate(rows):
        label, stance = (groups[i % len(groups)] if mock
                         else (r["viewpoint_group_label"], r["stance"]))
        articles.append({"link": r["link"], "viewpointGroupLabel": label, "stance": stance})
    summary = head["fact_summary"]
    briefing = head["common_facts_briefing"]
    if mock:
        # 목업임이 화면과 캡처에서 드러나게 한다
        summary = f"{summary} (샘플 요약)"
        briefing = f"{briefing} (샘플 브리핑)"
    return {
        "clusterId": head["cluster_id"],
        "category": head["category"],
        "factSummary": summary,
        "commonFactsBriefing": briefing,
        "clusteredAt": to_kst_iso(head["clustered_at"]),
        "articles": articles,
    }


def group_rows(rows):
    """기사당 한 줄인 표를 이슈별로 묶는다."""
    grouped = {}
    for row in rows:
        grouped.setdefault(row["cluster_id"], []).append(row)
    return grouped


def _preflight(broker):
    """보내기 전에 브로커 접속을 확인한다. 주소를 안 넣고 돌려 헛도는 사고를 막는다."""
    from confluent_kafka.admin import AdminClient
    if not broker:
        raise SystemExit("KAFKA_BROKER 가 비어 있습니다. infra/.env 를 확인하세요.")
    try:
        AdminClient({"bootstrap.servers": broker}).list_topics(timeout=10)
    except Exception as error:
        raise SystemExit(f"Kafka 브로커({broker})에 연결할 수 없습니다.") from error


def publish(messages, producer=None, rate=RATE_PER_SEC):
    """이슈별 메시지를 발행한다. 전달 확인이 끝난 건수를 돌려준다."""
    if producer is None:
        _preflight(BROKER)
        from confluent_kafka import Producer
        producer = Producer({"bootstrap.servers": BROKER, "acks": "all"})

    errors = []

    def on_delivery(error, _msg):
        if error is not None:
            errors.append(str(error))

    interval = 1.0 / rate if rate else 0
    next_slot = time.monotonic()
    for message in messages:
        if interval:
            now = time.monotonic()
            if now < next_slot:
                time.sleep(next_slot - now)
            next_slot = max(next_slot + interval, now)
        producer.produce(
            TOPIC,
            key=str(message["clusterId"]),  # BE 요구: key 는 clusterId 문자열
            value=json.dumps(message, ensure_ascii=False),
            on_delivery=on_delivery,
        )
        producer.poll(0)
    remaining = producer.flush(60)
    if remaining or errors:
        raise RuntimeError(
            f"전송 미확인 {remaining}건, 실패 {len(errors)}건 "
            f"(첫 오류: {errors[0] if errors else '없음'})")
    return len(messages)


def read_gold(day):
    """gold 이슈 피드에서 그 날짜 행을 읽는다.

    HDFS 는 WebHDFS 로 받아 임시 파일에 내려 읽는다. pyarrow 의 HDFS 연결은 자바 네이티브
    라이브러리를 요구해 컨테이너마다 되고 안 되는 것이 갈리는데, WebHDFS 는 http 라 어디서든
    된다(백업 잡에서 검증). 하루 분량이 1MB 남짓이라 내려받는 비용도 작다.
    """
    import shutil
    import tempfile
    import urllib.parse
    import urllib.request

    import pyarrow.parquet as pq

    local = os.environ.get("GOLD_LOCAL_ROOT")
    if local:  # 시험용 로컬 경로
        import pyarrow.dataset as ds
        return ds.dataset(f"{local}/dt={day}", format="parquet").to_table().to_pylist()

    path = f"{GOLD_PATH}/dt={day}"
    with urllib.request.urlopen(
            f"{WEBHDFS}{urllib.parse.quote(path)}?op=LISTSTATUS", timeout=60) as response:
        names = [f["pathSuffix"] for f in json.load(response)["FileStatuses"]["FileStatus"]
                 if f["pathSuffix"].endswith(".parquet")]
    if not names:
        raise SystemExit(f"gold 에 그 날짜가 없습니다: {path}")

    rows = []
    work = tempfile.mkdtemp()
    try:
        for name in names:
            target = os.path.join(work, name)
            url = f"{WEBHDFS}{urllib.parse.quote(f'{path}/{name}')}?op=OPEN"
            with urllib.request.urlopen(url, timeout=120) as response, open(target, "wb") as out:
                shutil.copyfileobj(response, out)
            rows.extend(pq.read_table(target).to_pylist())
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return rows


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("day", help="발행할 날짜 (gold 파티션)")
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="앞 2건만 출력하고 보내지 않음")
    group.add_argument("--send", action="store_true", help="실제 발행")
    ap.add_argument("--mock-viewpoints", action="store_true",
                    help="관점 라벨·성향·요약을 목업으로 채운다. DS 코드가 나오면 쓰지 않는다")
    args = ap.parse_args()

    rows = read_gold(args.day)
    grouped = group_rows(rows)
    messages = [build_message(v, mock=args.mock_viewpoints) for v in grouped.values()]
    messages.sort(key=lambda m: m["clusterId"])
    logger.info("%s: 이슈 %s개, 기사 %s건%s", args.day, f"{len(messages):,}", f"{len(rows):,}",
                ", 목업 채움" if args.mock_viewpoints else "")

    incomplete = [m for m in messages if missing_required(m)]
    if incomplete:
        logger.warning("필수 필드가 빈 이슈 %s개. 첫 이슈에서 빈 필드: %s",
                       f"{len(incomplete):,}", missing_required(incomplete[0]))

    if args.dry_run:
        for message in messages[:2]:
            print(json.dumps(message, ensure_ascii=False, indent=2)[:800])
    else:
        logger.info("발행 완료 %s건", f"{publish(messages):,}")
