"""silver 창을 DS 입력 JSONL 로 내려준다 (DS 연동).

DS 파이프라인(hannun-ingest)은 로컬 파일만 읽고 형식은 .json/.jsonl/.ndjson 만
받는다. silver 는 HDFS parquet 이라 그대로는 읽을 수 없어, 날짜별로 한 파일씩
로컬에 풀어준다. DS 코드는 손대지 않는다.

  <out>/dt=YYYY-MM-DD/articles.jsonl   (비압축, 한 줄에 기사 하나)

파일명이 .jsonl 이어야 한다 — DS 의 reader 는 .json 을 한 덩어리 JSON 으로 읽어서
확장자가 .json 이면 파싱이 깨진다. 그래서 Spark 쓰기 대신 드라이버에서 직접 쓴다.
하루치가 기사 몇천 건이라 이 방식으로 충분하고, 파일 이름과 개수를 정확히 맞출 수 있다.

같은 날짜를 다시 내려도 안전하다. 지난 날짜 파티션에도 기사가 뒤늦게 추가되므로
(RSS 가 며칠 전 기사를 준다) 최근 며칠을 다시 내리는 것을 전제로 만들었다.

  spark-submit --master local[*] jobs/silver_to_ds_input.py               # 어제(KST) 하루
  spark-submit --master local[*] jobs/silver_to_ds_input.py --recent 3    # 어제부터 3일
  spark-submit --master local[*] jobs/silver_to_ds_input.py 2026-09-01 2026-09-07
"""

import argparse
import datetime as dt
import json
import logging
import os

from pyspark.sql import SparkSession
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


def export_day(spark, day, out_root):
    """하루치를 <out_root>/dt=<day>/articles.jsonl 로 쓴다. 파티션이 없으면 None."""
    try:
        rows = spark.read.parquet(f"{SILVER}/dt={day}")
    except AnalysisException:
        logger.info("silver 에 없는 날짜, 건너뜀: %s", day)
        return None

    out_dir = os.path.join(out_root, f"dt={day}")
    os.makedirs(out_dir, exist_ok=True)
    final = os.path.join(out_dir, "articles.jsonl")
    staging = final + ".tmp"

    count = 0
    # toLocalIterator: 하루치를 드라이버 메모리에 한꺼번에 올리지 않고 흘려 쓴다
    with open(staging, "w", encoding="utf-8") as out:
        for row in rows.toLocalIterator():
            out.write(to_json_line(row) + "\n")
            count += 1
    # 다 쓴 뒤 제자리로 옮긴다 — DS 가 쓰는 중인 파일을 읽는 일을 막는다
    os.replace(staging, final)
    logger.info("내려주기 완료 %s: %s건 → %s", day, f"{count:,}", final)
    return count


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("dates", nargs="*", metavar="날짜", help="시작일 [끝일]. 생략하면 --recent 범위")
    ap.add_argument("--recent", type=int, default=1, help="어제부터 거슬러 며칠 (기본 1)")
    args = ap.parse_args()
    days = target_days(args.dates, args.recent)

    spark = (
        SparkSession.builder.appName("silver_to_ds_input")
        .config("spark.locality.wait", "0")  # bronze_to_silver 와 같은 이유 (local 모드 교착)
        .getOrCreate()
    )
    try:
        total = {day: export_day(spark, day, OUT_ROOT) for day in days}
        written = {d: n for d, n in total.items() if n is not None}
        logger.info("총 %d일, %s건", len(written), f"{sum(written.values()):,}")
    finally:
        spark.stop()
