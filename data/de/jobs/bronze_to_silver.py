"""bronze → silver 정형화 잡 (S15P21E105-68).

bronze 세 소스(news jsonl·news_dataset csv·bigkinds jsonl)를 article_v1 로 통일하고
article_id 중복을 제거해 /lake/silver/news/dt=<한국날짜>/ parquet 로 쓴다. 중복은
본문이 긴 레코드, 동률이면 crawled_at 이 최신인 레코드를 남긴다.
행 변환은 jobs/silver_transform.py 의 순수 함수, 이 파일은 Spark 배선만 담당한다.

  spark-submit --master local[*] jobs/bronze_to_silver.py --full
      세 소스 전체를 다시 읽어 silver 를 통째로 재구축 (초기 적재, 규칙 변경 시)
  spark-submit --master local[*] jobs/bronze_to_silver.py [--ingest-dates 2026-09-07 ...]
      지정 적재일(기본 오늘·어제)의 실시간분만 읽어 해당 dt 파티션만 덮어쓴다 (15분 DAG)

저장 형식은 환경변수 둘로 정한다 (S15P21E105-126). 둘 다 기본값이 parquet 이라 아무것도
주지 않으면 지금과 같다.

  SILVER_WRITE  parquet | iceberg | both   어디에 쓸지
  SILVER_READ   parquet | iceberg          증분이 기존 행을 어디서 읽을지

전환 순서는 아래와 같다. 읽기와 쓰기를 따로 켜는 이유가 여기 있다.

  1. SILVER_WRITE=both    두 곳에 같이 쓴다. 파케이가 최신으로 남아 언제든 되돌릴 수 있다
  2. SILVER_READ=iceberg  읽는 쪽을 옮긴다. 1 없이 이것만 하면 굳은 테이블을 읽게 된다
  3. SILVER_WRITE=iceberg 파케이 쓰기를 끊는다. 되돌리려면 파케이 재구축이 필요하다

  SILVER_WRITE=iceberg spark-submit --master local[*] --driver-memory 3g \
    --packages org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.9.1 \
    jobs/bronze_to_silver.py --full
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

import iceberg_conf  # noqa: E402
import metrics  # noqa: E402

logger = logging.getLogger("bronze_to_silver")

LAKE = os.environ.get("LAKE_ROOT", "hdfs://namenode:8020/lake")
SILVER = f"{LAKE}/silver/news"
SCHEMA = StructType([StructField(f, StringType(), f in NULLABLE) for f in FIELDS])

# 파케이가 기본이다. 옛 경로를 그대로 두고 옆에 Iceberg 테이블을 짓는 동안, 아무 설정도
# 주지 않은 잡은 지금과 똑같이 돌아야 한다 (S15P21E105-126)
TABLE = os.environ.get("SILVER_TABLE", f"{iceberg_conf.CATALOG}.silver.news")

# 읽기와 쓰기를 따로 켠다. 한 스위치로 묶으면 단계적 전환이 안 된다 — 쓰기를 both 로 둔
# 채 읽기만 옮겨야 파케이가 최신으로 남아 되돌리기가 환경변수 한 줄이 된다 (S15P21E105-126)
WRITE = os.environ.get("SILVER_WRITE", "parquet")   # parquet | iceberg | both
READ = os.environ.get("SILVER_READ", "parquet")     # parquet | iceberg
assert WRITE in ("parquet", "iceberg", "both"), f"SILVER_WRITE 값이 이상하다: {WRITE}"
assert READ in ("parquet", "iceberg"), f"SILVER_READ 값이 이상하다: {READ}"
WRITE_ICEBERG = WRITE in ("iceberg", "both")
WRITE_PARQUET = WRITE in ("parquet", "both")
USE_ICEBERG = WRITE_ICEBERG or READ == "iceberg"  # Iceberg 설정을 붙여야 하는가


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


def read_silver(spark):
    return spark.table(TABLE) if READ == "iceberg" else spark.read.parquet(SILVER)


def write(df, replace_all):
    """중복 제거가 끝난 결과를 쓴다. replace_all 이면 테이블을 통째로, 아니면 들어온 dt 만.

    중복 제거 셔플은 article_id 기준 200조각이라 그대로 쓰면 조각마다 날짜별 파일이 생겨
    dt 당 파일 195개가 됐다 (2026-09-07 실측 54만 파일). dt 로 재분배해 dt 당 1개로 쓴다.

    both 일 때 두 번 쓰므로 미리 담아 둔다. 담지 않으면 bronze 를 두 번 읽고 중복 제거도
    두 번 한다.
    """
    df = df.repartition("dt")
    if WRITE == "both":
        df = df.localCheckpoint()
    if WRITE_ICEBERG:
        writer = df.writeTo(TABLE)
        if replace_all:
            writer.partitionedBy(col("dt")).createOrReplace()
        else:
            # 들어온 dt 파티션만 갈아 끼운다. 파케이의 dynamic 덮어쓰기와 같은 동작이다
            writer.overwritePartitions()
    if WRITE_PARQUET:
        df.write.mode("overwrite").partitionBy("dt").parquet(SILVER)


def run_full(spark):
    crawled_at = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    dropped = {name: spark.sparkContext.accumulator(0) for name in ("dataset", "news", "bigkinds")}
    unknown = spark.sparkContext.accumulator({}, _CountByKey())
    rdd = (
        read_dataset(spark, crawled_at, dropped["dataset"], unknown)
        .union(read_news(spark, dropped["news"], unknown))
        .union(read_bigkinds(spark, dropped["bigkinds"], unknown))
    )
    write(dedup(to_df(spark, rdd)), replace_all=True)
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
    newest = (read_silver(spark).where(col("dt").isin(dts))
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
        existing = read_silver(spark).where(col("dt").isin(dts)).localCheckpoint()
    except AnalysisException:  # silver 가 아직 없음 (full 이전)
        existing = spark.createDataFrame([], SCHEMA)
    spark.conf.set("spark.sql.sources.partitionOverwriteMode", "dynamic")
    write(dedup(new.union(existing)), replace_all=False)
    logger.info("dt %s 갱신, 실시간 제외 %d건, 미등록 언론사 제외: %s", sorted(dts), dropped.value, unknown.value)
    metrics.push("bronze_to_silver", lambda: _incremental_lines(spark, dts, dropped, unknown))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true", help="세 소스 전체 재구축")
    ap.add_argument("--ingest-dates", nargs="+", help="반영할 bronze/news 적재일 (기본 오늘·어제)")
    args = ap.parse_args()


    builder = (
        SparkSession.builder.appName("bronze_to_silver")
        # local 모드의 파이썬 워커도 crawler·backfill·jobs 를 임포트해야 한다
        .config("spark.executorEnv.PYTHONPATH", ROOT)
        # 단일 노드라 데이터 지역성이 의미 없다. 기본 3초 대기를 두면 메모리에 고정한 파티션
        # (localCheckpoint) 태스크만 먼저 돌고 HDFS 태스크는 재스케줄 신호가 없어 영원히
        # 대기하는 local 모드 교착이 생긴다 (2026-09-07 실측)
        .config("spark.locality.wait", "0")
    )
    # Iceberg 설정은 쓸 때만 붙인다. 전역에 두면 jar 이 없는 순간 다른 잡까지 세션 생성에서
    # 죽는다 (iceberg_conf 주석 참고)
    spark = (iceberg_conf.configure(builder) if USE_ICEBERG else builder).getOrCreate()
    if USE_ICEBERG:
        spark.sql(f"CREATE NAMESPACE IF NOT EXISTS {TABLE.rsplit('.', 1)[0]}")
    if args.full:
        run_full(spark)
    else:
        today = dt.date.today()
        dates = args.ingest_dates or [str(today), str(today - dt.timedelta(days=1))]
        run_incremental(spark, dates)
    logger.info("silver 총 %s건", f"{read_silver(spark).count():,}")
    spark.stop()
