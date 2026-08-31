"""Spark→HDFS 왕복 검증 잡. 실전 적재 잡(S15P21E105-66)의 골격.

spark-submit --master local[*] jobs/hdfs_smoke.py
"""

from pyspark.sql import SparkSession

HDFS = "hdfs://namenode:8020"

spark = SparkSession.builder.appName("hdfs_smoke").getOrCreate()
path = f"{HDFS}/lake/_smoke_spark"

df = spark.createDataFrame([("smoke", 1)], ["k", "v"])
df.write.mode("overwrite").parquet(path)

back = spark.read.parquet(path)
assert back.count() == 1, "HDFS 에 쓴 행을 다시 읽지 못함"
print("PASS — spark→hdfs 왕복 정상")
spark.stop()
