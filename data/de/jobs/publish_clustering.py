"""gold 이슈 피드를 BE 로 발행한다 (S15P21E105-69).

토픽 news.clustering.completed, 이슈 하나가 메시지 하나, key 는 clusterId 문자열이다.
매번 전체를 보낸다(BE 협의). 같은 key 로 다시 가므로 BE 가 갱신으로 처리한다.

그래서 key 가 흔들리면 같은 사건이 BE 에 여러 이슈로 쌓인다. 재군집은 날짜가 바뀌면
같은 사건에 새 번호를 주므로, 보내기 직전에 최근 며칠간 나간 번호로 되돌린다
(stable_ids, S15P21E105-129). 근본 원인인 승계 실패는 DS 쪽에 남아 있다.

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

# 발행한 이슈 번호 기억 (S15P21E105-129). ds_input_export.json 과 같은 자리에 둔다
ISSUE_MAP = os.environ.get("PUBLISH_ISSUE_MAP", "/opt/airflow/state/publish_issue_map.json")
# 되돌아보는 날 수. DS 승계는 직전 창 하나만 보지만 발행은 DAG 를 멈추는 날이 있어
# 하루쯤 비어도 이어지도록 여유를 둔다
MAP_LOOKBACK_DAYS = int(os.environ.get("PUBLISH_MAP_LOOKBACK", "3"))
# 문턱은 DS 승계(SuccessionConfig)와 같은 값을 쓴다 — 두 곳이 다르게 판단하면 안 된다
MIN_SHARED = 2
MIN_OVERLAP_FRAC = 0.5

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
               if message.get(k) in (None, "", [])]
    for article in message["articles"]:
        for key in ("link", "viewpointGroupLabel", "stance"):
            if article.get(key) in (None, "") and f"articles[].{key}" not in missing:
                missing.append(f"articles[].{key}")
    return missing


def build_message(rows, mock=False, cluster_id=None):
    """한 이슈의 행들을 BE 스펙 메시지로 조립한다. rows 는 같은 cluster_id 의 행들.

    cluster_id 를 주면 그 번호로 나간다 — 어제 이슈를 이어받은 경우다(stable_ids).
    """
    rows = sorted(rows, key=lambda r: r["published_at"])
    head = rows[0]
    if cluster_id is None:
        cluster_id = head["cluster_id"]
    groups = mock_groups(cluster_id, len(rows)) if mock else None
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
        briefing = list(briefing or []) + ["(샘플 브리핑)"]
    return {
        "clusterId": cluster_id,
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


def load_issue_map(path):
    """날짜별 {기사 번호: 발행한 이슈 번호}. 없거나 깨졌으면 빈 값을 돌려준다.

    기억이 없으면 이어붙이기만 쉬고 발행은 그대로 간다. 모니터링 실패가 파이프라인을
    멈추면 안 된다는 metrics.py 와 같은 태도다.
    """
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        return {day: {a: int(i) for a, i in ids.items()} for day, ids in data.items()}
    except (FileNotFoundError, ValueError, AttributeError):
        return {}


def save_issue_map(path, issue_map, day, lookback=MAP_LOOKBACK_DAYS):
    """되돌아보는 범위 밖의 날은 버리고 저장한다. 안 버리면 파일이 끝없이 자란다."""
    floor = (dt.date.fromisoformat(day) - dt.timedelta(days=lookback)).isoformat()
    kept = {d: ids for d, ids in issue_map.items() if d >= floor}
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(kept, handle, ensure_ascii=False)
    os.replace(tmp, path)  # 쓰다 죽어도 반쯤 쓰인 파일이 남지 않는다
    return kept


def recent_ids(issue_map, day, lookback=MAP_LOOKBACK_DAYS):
    """최근 며칠간 기사가 어느 번호로 나갔는지 한 장으로 편다.

    같은 기사가 여러 날에 있으면 나중 날이 이긴다. 오늘이 맨 마지막이라, 하루 세 번
    도는 발행이 두 번째부터는 자기가 정한 번호를 다시 본다 — 하루 안에서 번호가
    흔들리지 않는 근거다.
    """
    floor = (dt.date.fromisoformat(day) - dt.timedelta(days=lookback)).isoformat()
    history = {}
    for stamp in sorted(d for d in issue_map if floor <= d <= day):
        history.update(issue_map[stamp])
    return history


def stable_ids(grouped, history):
    """이슈별로 쓸 발행 번호를 정한다. {gold 이슈 번호: 발행할 번호}.

    재군집은 같은 사건에 매일 새 번호를 준다. 기사는 안 바뀌므로, 이 이슈의 기사들이
    최근에 어느 번호로 나갔는지 득표해 과반이면 그 번호를 그대로 쓴다. 판정 규칙은
    DS 승계와 같다 — 다르게 판단하면 두 곳이 서로 다른 계보를 만든다.

    번호 하나를 둘이 가질 수는 없다. 쪼개지면 많이 겹치는 쪽이 가져가고, 오늘 그 번호를
    쓰는 다른 이슈가 이미 있으면 아무도 안 가져간다 — 키가 겹치면 BE 에서 두 이슈가
    서로를 덮어쓴다.
    """
    claims = {}
    for cluster_id, rows in grouped.items():
        votes = {}
        for row in rows:
            previous = history.get(row["article_id"])
            if previous is not None:
                votes[previous] = votes.get(previous, 0) + 1
        if not votes:
            continue
        # 동점이면 번호가 작은 쪽. 실행마다 결과가 달라지지 않게 한다
        previous_id, shared = min(votes.items(), key=lambda kv: (-kv[1], kv[0]))
        overlap = sum(votes.values())
        if shared >= MIN_SHARED and shared / overlap >= MIN_OVERLAP_FRAC:
            claims.setdefault(previous_id, []).append((shared, cluster_id))

    resolved = {cluster_id: cluster_id for cluster_id in grouped}
    for previous_id, entries in claims.items():
        winner = max(entries)[1]
        if previous_id in grouped and previous_id != winner:
            continue
        resolved[winner] = previous_id
    return resolved


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

    # 재군집이 매일 새로 매긴 번호를 어제 나간 번호로 되돌린다 (S15P21E105-129)
    issue_map = load_issue_map(ISSUE_MAP)
    resolved = stable_ids(grouped, recent_ids(issue_map, args.day))
    carried = sum(1 for k, v in resolved.items() if k != v)

    messages = [build_message(v, mock=args.mock_viewpoints, cluster_id=resolved[k])
                for k, v in grouped.items()]
    messages.sort(key=lambda m: m["clusterId"])
    logger.info("%s: 이슈 %s개, 기사 %s건, 어제 번호 이어받음 %s개%s",
                args.day, f"{len(messages):,}", f"{len(rows):,}", f"{carried:,}",
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
        # 보낸 뒤에만 기억한다. 못 보낸 번호를 기억하면 다음 실행이 헛것을 이어받는다
        issue_map[args.day] = {row["article_id"]: resolved[cluster_id]
                               for cluster_id, group in grouped.items() for row in group}
        save_issue_map(ISSUE_MAP, issue_map, args.day)
