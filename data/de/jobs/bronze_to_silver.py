"""bronze → silver 정형화 잡 (S15P21E105-68).

bronze 세 소스(news jsonl·news_dataset csv·bigkinds jsonl)를 article_v1 로 통일하고
article_id 중복을 제거해 /lake/silver/news/dt=<한국날짜>/ parquet 로 쓴다. 중복은
본문이 긴 레코드, 동률이면 crawled_at 이 최신인 레코드를 남긴다.
행 변환은 jobs/silver_transform.py 의 순수 함수, 이 파일은 Spark 배선만 담당한다.

  spark-submit --master local[*] jobs/bronze_to_silver.py --full
      세 소스 전체를 다시 읽어 silver 를 통째로 재구축 (초기 적재, 규칙 변경 시)
  spark-submit --master local[*] jobs/bronze_to_silver.py [--ingest-dates 2026-09-07 ...]
      지정 적재일(기본 오늘·어제)의 실시간분만 읽어 해당 dt 파티션만 덮어쓴다 (15분 DAG)
"""

import argparse
import datetime as dt
import logging
import os
import sys

from pyspark.sql import SparkSession, Window
from pyspark.sql.functions import col, length, row_number
from pyspark.sql.types import StringType, StructField, StructType
from pyspark.sql.utils import AnalysisException

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # crawler·backfill·jobs 의 부모
sys.path.insert(0, ROOT)
from jobs.silver_transform import (  # noqa: E402
    FIELDS, NULLABLE, from_bigkinds_line, from_dataset_row, from_realtime_message,
)

logger = logging.getLogger("bronze_to_silver")

LAKE = os.environ.get("LAKE_ROOT", "hdfs://namenode:8020/lake")
SILVER = f"{LAKE}/silver/news"
SCHEMA = StructType([StructField(f, StringType(), f in NULLABLE) for f in FIELDS])


def _counting(fn, dropped):
    """변환 결과가 None 이면 누산기에 더한다 — 제외 건수를 잡 로그로 남기기 위함."""
    def wrapped(*args):
        record = fn(*args)
        if record is None:
            dropped.add(1)
        return record
    return wrapped


def read_dataset(spark, crawled_at, dropped):
    df = (
        spark.read.option("sep", "|").option("header", True).option("multiLine", True)
        .option("quote", '"').option("escape", '"')
        .csv(f"{LAKE}/bronze/news_dataset/*.csv")
    )
    tx = _counting(from_dataset_row, dropped)
    return df.rdd.map(lambda r: tx(list(r), crawled_at))


def read_news(spark, dropped, ingest_dates=None):
    df = spark.read.text(f"{LAKE}/bronze/news")  # ingest_date= 파티션 컬럼이 따라온다
    if ingest_dates:
        df = df.where(col("ingest_date").isin(ingest_dates))
    tx = _counting(from_realtime_message, dropped)
    return df.rdd.map(lambda r: tx(r["value"], str(r["ingest_date"])))


def read_bigkinds(spark, dropped):
    tx = _counting(from_bigkinds_line, dropped)
    return spark.read.text(f"{LAKE}/bronze/bigkinds/*.jsonl").rdd.map(lambda r: tx(r["value"]))


def to_df(spark, rdd):
    rows = rdd.filter(lambda d: d is not None).map(lambda d: [d[f] for f in FIELDS])
    return spark.createDataFrame(rows, SCHEMA)


def dedup(df):
    order = Window.partitionBy("article_id").orderBy(length(col("article")).desc(), col("crawled_at").desc())
    return df.withColumn("_rn", row_number().over(order)).where(col("_rn") == 1).drop("_rn")


def run_full(spark):
    crawled_at = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    dropped = {name: spark.sparkContext.accumulator(0) for name in ("dataset", "news", "bigkinds")}
    rdd = (
        read_dataset(spark, crawled_at, dropped["dataset"])
        .union(read_news(spark, dropped["news"]))
        .union(read_bigkinds(spark, dropped["bigkinds"]))
    )
    dedup(to_df(spark, rdd)).write.mode("overwrite").partitionBy("dt").parquet(SILVER)
    logger.info("제외 건수: %s", {k: v.value for k, v in dropped.items()})


def run_incremental(spark, ingest_dates):
    dropped = spark.sparkContext.accumulator(0)
    new = to_df(spark, read_news(spark, dropped, ingest_dates))
    dts = [r["dt"] for r in new.select("dt").distinct().collect()]
    if not dts:
        logger.info("적재일 %s 에 신규 기사 없음", ingest_dates)
        return
    try:
        # 덮어쓸 파티션의 기존 행을 메모리에 먼저 고정한다. 읽는 경로에 쓰기를 막는 Spark
        # 검사를 통과시키고, 덮어쓰기 도중 원본이 지워져도 읽기가 끊기지 않게 하기 위함
        existing = spark.read.parquet(SILVER).where(col("dt").isin(dts)).localCheckpoint()
    except AnalysisException:  # silver 가 아직 없음 (full 이전)
        existing = spark.createDataFrame([], SCHEMA)
    spark.conf.set("spark.sql.sources.partitionOverwriteMode", "dynamic")
    dedup(new.union(existing)).write.mode("overwrite").partitionBy("dt").parquet(SILVER)
    logger.info("dt %s 갱신, 실시간 제외 %d건", sorted(dts), dropped.value)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true", help="세 소스 전체 재구축")
    ap.add_argument("--ingest-dates", nargs="+", help="반영할 bronze/news 적재일 (기본 오늘·어제)")
    args = ap.parse_args()

    spark = (
        SparkSession.builder.appName("bronze_to_silver")
        # local 모드의 파이썬 워커도 crawler·backfill·jobs 를 임포트해야 한다
        .config("spark.executorEnv.PYTHONPATH", ROOT)
        # 단일 노드라 데이터 지역성이 의미 없다. 기본 3초 대기를 두면 메모리에 고정한 파티션
        # (localCheckpoint) 태스크만 먼저 돌고 HDFS 태스크는 재스케줄 신호가 없어 영원히
        # 대기하는 local 모드 교착이 생긴다 (2026-09-07 실측)
        .config("spark.locality.wait", "0")
        .getOrCreate()
    )
    if args.full:
        run_full(spark)
    else:
        today = dt.date.today()
        dates = args.ingest_dates or [str(today), str(today - dt.timedelta(days=1))]
        run_incremental(spark, dates)
    logger.info("silver 총 %s건", f"{spark.read.parquet(SILVER).count():,}")
    spark.stop()
