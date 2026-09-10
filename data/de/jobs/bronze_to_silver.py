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

from pyspark import AccumulatorParam
from pyspark.sql import SparkSession, Window
from pyspark.sql.functions import col, length, row_number
from pyspark.sql.types import StringType, StructField, StructType
from pyspark.sql.utils import AnalysisException

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # crawler·backfill·jobs 의 부모
sys.path.insert(0, ROOT)
from jobs.silver_transform import (  # noqa: E402
    FIELDS, NULLABLE, UnknownPublisher, from_bigkinds_line, from_dataset_row, from_realtime_message,
)

import metrics  # noqa: E402

logger = logging.getLogger("bronze_to_silver")

LAKE = os.environ.get("LAKE_ROOT", "hdfs://namenode:8020/lake")
SILVER = f"{LAKE}/silver/news"
SCHEMA = StructType([StructField(f, StringType(), f in NULLABLE) for f in FIELDS])


class _CountByKey(AccumulatorParam):
    """{언론사: 건수} 누산기."""

    def zero(self, value):
        return {}

    def addInPlace(self, a, b):
        for key, n in b.items():
            a[key] = a.get(key, 0) + n
        return a


def _counting(fn, dropped, unknown):
    """제외된 행을 센다. None 은 dropped 에, 미등록 언론사는 unknown 에 이름별로."""
    def wrapped(*args):
        try:
            record = fn(*args)
        except UnknownPublisher as error:
            unknown.add({error.args[0]: 1})
            return None
        if record is None:
            dropped.add(1)
        return record
    return wrapped


def read_dataset(spark, crawled_at, dropped, unknown):
    df = (
        spark.read.option("sep", "|").option("header", True).option("multiLine", True)
        .option("quote", '"').option("escape", '"')
        .csv(f"{LAKE}/bronze/news_dataset/*.csv")
    )
    tx = _counting(from_dataset_row, dropped, unknown)
    return df.rdd.map(lambda r: tx(list(r), crawled_at))


def read_news(spark, dropped, unknown, ingest_dates=None):
    # ingest_date=* 로 읽는 이유: 폴더 뿌리를 그대로 읽으면 Spark 가 스트리밍 sink 의 파일
    # 목록 장부(_spark_metadata)만 신뢰해서, 새벽 합치기(S15P21E105-74)로 바뀐 파일을 못 본다.
    # basePath 를 주면 장부를 거치지 않고도 ingest_date 파티션 컬럼이 그대로 따라온다
    df = (spark.read.option("basePath", f"{LAKE}/bronze/news")
          .text(f"{LAKE}/bronze/news/ingest_date=*"))
    if ingest_dates:
        df = df.where(col("ingest_date").isin(ingest_dates))
    tx = _counting(from_realtime_message, dropped, unknown)
    return df.rdd.map(lambda r: tx(r["value"], str(r["ingest_date"])))


def read_bigkinds(spark, dropped, unknown):
    tx = _counting(from_bigkinds_line, dropped, unknown)
    return spark.read.text(f"{LAKE}/bronze/bigkinds/*.jsonl").rdd.map(lambda r: tx(r["value"]))


def to_df(spark, rdd):
    rows = rdd.filter(lambda d: d is not None).map(lambda d: [d[f] for f in FIELDS])
    return spark.createDataFrame(rows, SCHEMA)


def dedup(df):
    order = Window.partitionBy("article_id").orderBy(length(col("article")).desc(), col("crawled_at").desc())
    return df.withColumn("_rn", row_number().over(order)).where(col("_rn") == 1).drop("_rn")


def write(df):
    # 중복 제거 셔플은 article_id 기준 200조각이라 그대로 쓰면 조각마다 날짜별 파일이 생겨
    # dt 당 파일 195개가 됐다 (2026-09-07 실측 54만 파일). dt 로 재분배해 dt 당 1개로 쓴다
    df.repartition("dt").write.mode("overwrite").partitionBy("dt").parquet(SILVER)


def run_full(spark):
    crawled_at = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    dropped = {name: spark.sparkContext.accumulator(0) for name in ("dataset", "news", "bigkinds")}
    unknown = spark.sparkContext.accumulator({}, _CountByKey())
    rdd = (
        read_dataset(spark, crawled_at, dropped["dataset"], unknown)
        .union(read_news(spark, dropped["news"], unknown))
        .union(read_bigkinds(spark, dropped["bigkinds"], unknown))
    )
    write(dedup(to_df(spark, rdd)))
    logger.info("제외 건수: %s", {k: v.value for k, v in dropped.items()})
    logger.info("미등록 언론사 제외: %s", unknown.value)


def _incremental_lines(spark, dts, dropped, unknown):
    """15분 배치 지표 (S15P21E105-79).

    적재 지연은 갱신한 파티션의 가장 늦은 발행 시각과 지금의 차다. crawled_at 으로는
    못 잰다 — 실시간분의 crawled_at 은 적재일 자정으로 근사한 값이다.
    """
    lines = [
        metrics.line("silver_partitions_updated", len(dts)),
        metrics.line("silver_dropped_rows", dropped.value),
    ]
    lines += [metrics.line("silver_unknown_publisher_rows", count, {"publisher": name})
              for name, count in unknown.value.items()]
    newest = (spark.read.parquet(SILVER).where(col("dt").isin(dts))
              .agg({"published": "max"}).collect()[0][0])
    if newest:
        seen = dt.datetime.strptime(newest, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
        lines.append(metrics.line(
            "ingest_lag_seconds", int((dt.datetime.now(dt.timezone.utc) - seen).total_seconds())))
    return lines


def run_incremental(spark, ingest_dates):
    dropped = spark.sparkContext.accumulator(0)
    unknown = spark.sparkContext.accumulator({}, _CountByKey())
    new = to_df(spark, read_news(spark, dropped, unknown, ingest_dates))
    dts = [r["dt"] for r in new.select("dt").distinct().collect()]
    if not dts:
        logger.info("적재일 %s 에 신규 기사 없음", ingest_dates)
        metrics.push("bronze_to_silver", [metrics.line("silver_partitions_updated", 0)])
        return
    try:
        # 덮어쓸 파티션의 기존 행을 메모리에 먼저 고정한다. 읽는 경로에 쓰기를 막는 Spark
        # 검사를 통과시키고, 덮어쓰기 도중 원본이 지워져도 읽기가 끊기지 않게 하기 위함
        existing = spark.read.parquet(SILVER).where(col("dt").isin(dts)).localCheckpoint()
    except AnalysisException:  # silver 가 아직 없음 (full 이전)
        existing = spark.createDataFrame([], SCHEMA)
    spark.conf.set("spark.sql.sources.partitionOverwriteMode", "dynamic")
    write(dedup(new.union(existing)))
    logger.info("dt %s 갱신, 실시간 제외 %d건, 미등록 언론사 제외: %s", sorted(dts), dropped.value, unknown.value)
    metrics.push("bronze_to_silver", lambda: _incremental_lines(spark, dts, dropped, unknown))


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
