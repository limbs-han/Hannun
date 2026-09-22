"""bronze/news 파티션 파일 합치기 (S15P21E105-74).

15분 배치가 Kafka 파티션 3개를 각각 쓰는 탓에 하루 파티션에 파일이 200~270개 쌓인다.
어제 파티션을 읽어 파일 1개로 다시 쓰고, 줄 수가 같을 때만 원본과 교체한다.
줄 수가 다르면 원본을 그대로 두고 실패한다 — bronze 는 유실이 곧 복구 불가다.

주의: 이 폴더에는 스트리밍 sink 가 남긴 파일 목록 장부(_spark_metadata)가 있다. 합치면
장부와 실제 파일이 어긋나므로, 읽는 쪽(bronze_to_silver)은 장부를 거치지 않고 폴더를
직접 읽어야 한다. 쓰는 쪽(kafka_to_bronze)은 장부에 이어 붙이기만 해서 영향이 없다.

  spark-submit --master local[*] jobs/compact_bronze.py            # 어제 파티션
  spark-submit --master local[*] jobs/compact_bronze.py 2026-09-05  # 날짜 지정
"""

import datetime as dt
import logging
import os
import sys

from py4j.protocol import Py4JJavaError
from pyspark.sql import SparkSession

logger = logging.getLogger("compact_bronze")

LAKE = os.environ.get("LAKE_ROOT", "hdfs://namenode:8020/lake")  # bronze_to_silver 와 같은 변수


def _hadoop(spark):
    jvm = spark.sparkContext._jvm
    conf = spark.sparkContext._jsc.hadoopConfiguration()
    return jvm.org.apache.hadoop.fs.FileSystem.get(jvm.java.net.URI(LAKE), conf), jvm


def compact(spark, ingest_date):
    """한 파티션을 파일 1개로 합친다. 합친 건수를 돌려주고, 합칠 게 없으면 None."""
    fs, jvm = _hadoop(spark)
    path = lambda p: jvm.org.apache.hadoop.fs.Path(p)  # noqa: E731
    src = f"{LAKE}/bronze/news/ingest_date={ingest_date}"
    staging, old = f"{LAKE}/_staging/compact_{ingest_date}", f"{src}__old"

    if not fs.exists(path(src)):
        logger.info("파티션 없음, 건너뜀: %s", ingest_date)
        return None
    before = len([f for f in fs.listStatus(path(src)) if f.getPath().getName().startswith("part-")])
    if before <= 1:
        logger.info("이미 파일 %d개, 건너뜀: %s", before, ingest_date)
        return None

    rows = spark.read.text(src).count()
    spark.read.text(src).repartition(1).write.mode("overwrite").text(staging)
    merged = spark.read.text(staging).count()
    if merged != rows:
        raise RuntimeError(f"줄 수 불일치({ingest_date}): 원본 {rows:,} vs 합본 {merged:,} — 원본 유지")

    # 원본을 먼저 옆으로 치우고 합본을 제자리에 놓는다. 중간에 죽어도 __old 가 남아 복구 가능
    for target in (old,):
        if fs.exists(path(target)):
            fs.delete(path(target), True)
    fs.rename(path(src), path(old))
    fs.rename(path(staging), path(src))
    fs.delete(path(old), True)
    logger.info("합치기 완료 %s: 파일 %d개 → 1개, %s건", ingest_date, before, f"{rows:,}")
    return rows


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    target = sys.argv[1] if len(sys.argv) > 1 else str(dt.date.today() - dt.timedelta(days=1))
    spark = (
        SparkSession.builder.appName("compact_bronze")
        .config("spark.locality.wait", "0")  # bronze_to_silver 와 같은 이유 (local 모드 교착)
        .getOrCreate()
    )
    try:
        compact(spark, target)
    except Py4JJavaError as error:
        raise RuntimeError(f"HDFS 작업 실패({target}): {error.java_exception.getMessage()}") from error
    finally:
        spark.stop()
