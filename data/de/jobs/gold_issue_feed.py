"""DS 분석 산출물을 서빙용 이슈 피드 표로 합친다 (S15P21E105-69).

DS 사슬은 이슈 번호와 기사 번호만 남기고 제목·링크는 다른 표에 있다. 셋을 합쳐 BE 가
받는 모양 하나로 만들어 /lake/gold/issue_feed/dt=<한국날짜>/ 에 쌓는다. 발행기가 이 표를
읽으므로, 어제 것을 다시 보내달라는 요청에 DS 사슬을 다시 돌리지 않아도 된다.

관점 라벨과 성향, 요약은 DS 코드가 아직 없어 비워 둔다. 표에는 사실만 담고, 목업으로
채우는 것은 발행할 때 고른다.

DS gold 는 로컬 경로다. DS 코드가 HDFS 를 쓰지 못해 그대로 두고 읽기 전용으로 붙인다.

  spark-submit --master local[*] jobs/gold_issue_feed.py            # 오늘(KST)
  spark-submit --master local[*] jobs/gold_issue_feed.py 2026-09-08
"""

import argparse
import datetime as dt
import logging
import os

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

logger = logging.getLogger("gold_issue_feed")

LAKE = os.environ.get("LAKE_ROOT", "hdfs://namenode:8020/lake")
GOLD = f"{LAKE}/gold/issue_feed"
DS_GOLD = os.environ.get("DS_GOLD_ROOT", "/opt/airflow/ds_gold")
KST = dt.timezone(dt.timedelta(hours=9))

# 이슈 하나가 메시지 하나가 된다. 기사는 배열로 들어가므로 표에서는 기사당 한 줄로 펼쳐 두고
# 발행기가 이슈 번호로 묶는다. 표를 펼쳐 두면 Spark 로 세거나 확인하기 쉽다
COLUMNS = [
    "cluster_id", "category", "fact_summary", "common_facts_briefing", "clustered_at",
    "link", "viewpoint_group_label", "stance", "publisher_id", "published_at",
    "article_id", "issue_size", "publishers", "hot_score", "is_representative",
]


def today_kst(now=None):
    return str((now or dt.datetime.now(dt.timezone.utc)).astimezone(KST).date())


def build(spark, day):
    """DS 표 셋을 합쳐 기사당 한 줄인 표를 만든다."""
    summary = spark.read.parquet(f"file://{DS_GOLD}/issue_summary")
    registry = spark.read.parquet(f"file://{DS_GOLD}/issue_registry")
    articles = spark.read.parquet(f"file://{DS_GOLD}/articles")

    # 같은 이슈가 여러 창에 있으면 가장 최근 계산본만 쓴다
    latest = summary.groupBy("issue_id").agg(F.max("summarized_at").alias("summarized_at"))
    summary = summary.join(latest, ["issue_id", "summarized_at"])
    registry = registry.join(
        registry.groupBy("issue_id").agg(F.max("succeeded_at").alias("succeeded_at")),
        ["issue_id", "succeeded_at"])

    rep = articles.select(
        F.col("article_id").alias("representative"),
        F.col("category").alias("rep_category"),
        F.col("title").alias("rep_title"),
        F.col("content").alias("rep_content"))
    member = articles.select(
        "article_id", "url", "publisher_id", "published_at")

    joined = (summary.join(rep, "representative")
              .join(registry.select("issue_id", "article_id"), "issue_id")
              .join(member, "article_id"))

    return (joined
            .select(
                F.col("issue_id").alias("cluster_id"),
                F.col("rep_category").alias("category"),
                F.col("rep_title").alias("fact_summary"),
                # 요약 코드가 없어 대표 기사 본문 앞부분을 넣는다. 발행기가 목업 표시를 붙인다
                F.substring(F.regexp_replace(F.col("rep_content"), r"\s+", " "), 1, 200)
                 .alias("common_facts_briefing"),
                F.col("summarized_at").alias("clustered_at"),
                F.col("url").alias("link"),
                # DS 관점 분류가 없어 비워 둔다. 표에는 사실만 담는다
                F.lit(None).cast("string").alias("viewpoint_group_label"),
                F.lit(None).cast("string").alias("stance"),
                "publisher_id", "published_at", "article_id",
                "issue_size", "publishers", "hot_score",
                (F.col("article_id") == F.col("representative")).alias("is_representative"))
            .withColumn("dt", F.lit(day)))


def write(df, day):
    (df.repartition(1)  # 하루 분량이 1MB 남짓이라 파일 하나로 충분하다
       .write.mode("overwrite")
       .option("partitionOverwriteMode", "dynamic")
       .partitionBy("dt").parquet(GOLD))
    logger.info("gold 이슈 피드 %s: 이슈 %s개, 기사 %s건",
                day, f"{df.select('cluster_id').distinct().count():,}", f"{df.count():,}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("day", nargs="?", help="쌓을 날짜. 생략하면 오늘(KST)")
    args = ap.parse_args()
    day = args.day or today_kst()

    spark = (SparkSession.builder.appName("gold_issue_feed")
             .config("spark.locality.wait", "0")  # bronze_to_silver 와 같은 이유
             .getOrCreate())
    try:
        write(build(spark, day), day)
    finally:
        spark.stop()
