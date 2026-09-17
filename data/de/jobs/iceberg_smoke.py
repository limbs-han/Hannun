"""Iceberg 카탈로그 동작 확인 (S15P21E105-126 1단계).

시험 테이블 하나를 만들어 쓰고 읽고 지운다. 기존 데이터는 건드리지 않는다.
2단계 이후에 쓸 기능 셋을 여기서 미리 확인한다 — 테이블 생성, MERGE 로 부분 수정,
스냅샷 이력. 셋 중 하나라도 안 되면 다음 단계로 가지 않는다.

  spark-submit --master local[*] \
    --packages org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.9.1 \
    /opt/airflow/jobs/iceberg_smoke.py

패키지 버전이 안 맞으면 SparkSession 생성 단계에서 클래스를 못 찾는다고 멈춘다.
Spark 3.5·Scala 2.12 조합이라 iceberg-spark-runtime-3.5_2.12 계열을 쓰고, 1.9.1 이
받아지지 않으면 1.8.1 로 낮춰 본다.
"""

from pyspark.sql import SparkSession

import iceberg_conf

spark = iceberg_conf.configure(
    SparkSession.builder.appName("iceberg_smoke")).getOrCreate()

NS = f"{iceberg_conf.CATALOG}.smoke"
TABLE = f"{NS}.t"

spark.sql(f"CREATE NAMESPACE IF NOT EXISTS {NS}")
spark.sql(f"DROP TABLE IF EXISTS {TABLE} PURGE")
spark.sql(f"CREATE TABLE {TABLE} (k string, v int) USING iceberg")

spark.sql(f"INSERT INTO {TABLE} VALUES ('a', 1), ('b', 2)")
assert spark.table(TABLE).count() == 2, "쓴 두 줄을 다시 읽지 못함"

# 4단계 증분 갱신이 이 문장을 쓴다. 있으면 고치고 없으면 넣는다
spark.sql(f"""
    MERGE INTO {TABLE} t
    USING (SELECT 'a' AS k, 9 AS v UNION ALL SELECT 'c' AS k, 3 AS v) s
    ON t.k = s.k
    WHEN MATCHED THEN UPDATE SET t.v = s.v
    WHEN NOT MATCHED THEN INSERT *
""")
rows = {r["k"]: r["v"] for r in spark.table(TABLE).collect()}
assert rows == {"a": 9, "b": 2, "c": 3}, f"MERGE 결과가 다름: {rows}"

# 되돌리기의 근거. 쓸 때마다 한 줄씩 쌓인다
snapshots = spark.sql(f"SELECT * FROM {TABLE}.snapshots").count()
assert snapshots >= 3, f"스냅샷 이력이 남지 않음: {snapshots}"

spark.sql(f"DROP TABLE {TABLE} PURGE")
print(f"PASS — iceberg 카탈로그 정상 (스냅샷 {snapshots}개 기록 확인)")
spark.stop()
