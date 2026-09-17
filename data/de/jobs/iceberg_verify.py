"""옛 파케이와 새 Iceberg 테이블을 대조한다 (S15P21E105-126 2단계 합격 판정).

전환의 합격 기준은 "돌아가는 것 같다"가 아니라 건수가 같은 것이다. 총 건수와 날짜별
건수를 비교하고, 어긋나는 날짜를 최대 20개까지 찍는다. 읽기만 하므로 몇 번 돌려도 된다.

대조 중에는 15분 배치를 멈춰 둔다. 파케이가 갱신되면 기준이 움직인다.

  spark-submit --master local[*] --driver-memory 2g \
    --packages org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.9.1 \
    /opt/airflow/jobs/iceberg_verify.py

전체 재구축은 모든 bronze 를 다시 읽으므로, 날짜별로 조금씩 늘어난 것은 정상일 수 있다.
15분 배치는 오늘·어제만 반영해서 늦게 들어온 기사가 옛 파케이에 빠져 있을 수 있다.
줄어든 날짜가 있으면 그것이 문제다.
"""

import os
import sys

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

import iceberg_conf

LAKE = os.environ.get("LAKE_ROOT", "hdfs://namenode:8020/lake")
PARQUET = f"{LAKE}/silver/news"
TABLE = os.environ.get("SILVER_TABLE", f"{iceberg_conf.CATALOG}.silver.news")

spark = iceberg_conf.configure(
    SparkSession.builder.appName("iceberg_verify")).getOrCreate()

old = spark.read.parquet(PARQUET)
new = spark.table(TABLE)

old_total, new_total = old.count(), new.count()
print(f"파케이 {old_total:,}건 / Iceberg {new_total:,}건 / 차이 {new_total - old_total:+,}")

by_dt = (
    old.groupBy("dt").count().withColumnRenamed("count", "old")
    .join(new.groupBy("dt").count().withColumnRenamed("count", "new"), "dt", "full_outer")
    .fillna(0, ["old", "new"])
    .withColumn("diff", F.col("new") - F.col("old"))
)
gaps = by_dt.where(F.col("diff") != 0).orderBy(F.col("diff"))
n_gaps = gaps.count()

print(f"날짜 {by_dt.count():,}개 중 어긋난 날짜 {n_gaps:,}개")
if n_gaps:
    print("줄어든 쪽부터 20개:")
    gaps.show(20, truncate=False)
    lost = gaps.where(F.col("diff") < 0).agg(F.sum("diff")).collect()[0][0] or 0
    print(f"Iceberg 에서 줄어든 총 건수: {lost:,}")

# 같은 기사가 두 줄로 들어가지 않았는지. 중복 제거가 깨졌으면 여기서 잡힌다
dups = new.groupBy("article_id").count().where(F.col("count") > 1).count()
print(f"article_id 중복: {dups:,}건")

spark.stop()
sys.exit(1 if dups else 0)
