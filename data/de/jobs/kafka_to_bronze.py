"""Kafka news.article.raw → HDFS bronze 적재 잡 (S15P21E105-66).

원본 보존 계층 — Kafka value(JSON)를 파싱·변형 없이 줄 단위(jsonl)로 쌓는다.
체크포인트가 소비 위치를 기억하므로 재실행해도 중복·누락 없다(파일 싱크 exactly-once).
경로 규칙은 data/docs/lake-layout.md.

spark-submit --master local[*] \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.4 \
  jobs/kafka_to_bronze.py
"""

import os

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, current_date

HDFS = "hdfs://namenode:8020"
TOPIC = "news.article.raw"

broker = os.environ.get("KAFKA_BROKER")
assert broker, "KAFKA_BROKER 미설정 — infra/.env 확인"

spark = SparkSession.builder.appName("kafka_to_bronze").getOrCreate()

stream = (
    spark.readStream.format("kafka")
    .option("kafka.bootstrap.servers", broker)
    .option("subscribe", TOPIC)
    .option("startingOffsets", "earliest")
    # 배치당 상한 — 백필로 토픽에 수십만 건 쌓여도 한 번에 다 못 삼켜 죽는 일 방지
    .option("maxOffsetsPerTrigger", 100_000)
    .load()
)

query = (
    stream.select(col("value").cast("string"))
    .withColumn("ingest_date", current_date())
    .writeStream.format("text")  # value 한 컬럼을 그대로 줄로 — 결과 파일이 곧 jsonl
    .partitionBy("ingest_date")
    .option("path", f"{HDFS}/lake/bronze/news")
    .option("checkpointLocation", f"{HDFS}/lake/_checkpoints/bronze_news")
    # availableNow = 지금 쌓인 것까지만 처리하고 종료. 상주 스트림 대신 15분 배치(DAG)로 운영
    .trigger(availableNow=True)
    .start()
)
query.awaitTermination()
spark.stop()
