"""DS 분석 산출물을 서빙용 이슈 피드 표로 합친다 (S15P21E105-69).

DS 사슬은 이슈 번호와 기사 번호만 남기고 제목·링크는 다른 표에 있다. 셋을 합쳐 BE 가
받는 모양 하나로 만들어 /lake/gold/issue_feed/dt=<한국날짜>/ 에 쌓는다. 발행기가 이 표를
읽으므로, 어제 것을 다시 보내달라는 요청에 DS 사슬을 다시 돌리지 않아도 된다.

관점 라벨과 성향, 요약은 DS2 가 계산해 ds_output 에 JSONL 로 둔다. 있으면 붙이고 없으면
비워 둔다. 비어 있으면 발행기가 목업으로 채울지 고르게 된다.

DS gold 와 ds_output 은 로컬 경로다. DS 코드가 HDFS 를 쓰지 못해 그대로 두고 읽기
전용으로 붙인다.

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
DS_OUTPUT = os.environ.get("DS_OUTPUT_ROOT", "/opt/airflow/ds_output")
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


def read_ds2(spark):
    """DS2 분석 결과를 기사당 한 줄로 펼쳐 읽는다. 파일이 없으면 None.

    DS2 는 BE 스펙 모양의 JSONL 을 둔다. 이슈 하나가 한 줄이고 기사가 배열이라, 붙이려면
    배열을 펼쳐야 한다. 붙이는 키는 clusterId 와 link 다.
    """
    if not os.path.isdir(DS_OUTPUT) or not [f for f in os.listdir(DS_OUTPUT)
                                            if f.endswith(".jsonl")]:
        logger.info("ds_output 에 파일이 없어 관점 값을 비워 둔다: %s", DS_OUTPUT)
        return None
    raw = spark.read.json(f"file://{DS_OUTPUT}/*.jsonl")
    # 같은 창을 다시 돌려 파일이 겹치면 계산 시각이 늦은 것을 쓴다
    newest = raw.groupBy("clusterId").agg(F.max("clusteredAt").alias("clusteredAt"))
    raw = raw.join(newest, ["clusterId", "clusteredAt"])
    article = F.explode("articles").alias("article")
    return (raw.select(F.col("clusterId").alias("cluster_id"),
                       F.col("factSummary").alias("ds2_fact_summary"),
                       F.col("commonFactsBriefing").alias("ds2_briefing"),
                       F.col("category").alias("ds2_category"), article)
            .select("cluster_id", "ds2_fact_summary", "ds2_briefing", "ds2_category",
                    F.col("article.link").alias("link"),
                    F.col("article.viewpointGroupLabel").alias("ds2_label"),
                    F.col("article.stance").alias("ds2_stance"))
            .dropDuplicates(["cluster_id", "link"]))


def merge_ds2(feed, ds2):
    """DS2 값을 붙인다. 없는 자리는 비워 두고, 붙지 않은 건수를 로그로 남긴다."""
    if ds2 is None:
        return feed
    joined = feed.join(ds2, ["cluster_id", "link"], "left")
    matched = joined.where(F.col("ds2_stance").isNotNull()).count()
    logger.info("DS2 붙은 기사 %s건 / 전체 %s건", f"{matched:,}", f"{feed.count():,}")
    only_ds2 = ds2.join(feed.select("cluster_id", "link"), ["cluster_id", "link"], "left_anti").count()
    if only_ds2:
        # DS2 에만 있는 기사는 우리 표에 없는 것이다. 링크나 이슈 번호가 어긋났다는 신호다
        logger.warning("우리 표에 없는 DS2 기사 %s건 — 링크·이슈 번호 대조 필요", f"{only_ds2:,}")
    return (joined
            .withColumn("viewpoint_group_label", F.coalesce("ds2_label", "viewpoint_group_label"))
            .withColumn("stance", F.coalesce("ds2_stance", "stance"))
            .withColumn("fact_summary", F.coalesce("ds2_fact_summary", "fact_summary"))
            .withColumn("common_facts_briefing", F.coalesce("ds2_briefing", "common_facts_briefing"))
            .withColumn("category", F.coalesce("ds2_category", "category"))
            .drop("ds2_label", "ds2_stance", "ds2_fact_summary", "ds2_briefing", "ds2_category"))


def build(spark, day):
    """DS 표 셋을 합쳐 기사당 한 줄인 표를 만들고 DS2 분석 값을 붙인다."""
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


def build_with_ds2(spark, day):
    return merge_ds2(build(spark, day), read_ds2(spark))


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
        write(build_with_ds2(spark, day), day)
    finally:
        spark.stop()
