"""DS 분석 산출물을 서빙용 이슈 피드 표로 합친다 (S15P21E105-69).

DS 사슬은 이슈 번호와 기사 번호만 남기고 제목·링크는 다른 표에 있다. 셋을 합쳐 BE 가
받는 모양 하나로 만들어 /lake/gold/issue_feed/dt=<한국날짜>/ 에 쌓는다. 발행기가 이 표를
읽으므로, 어제 것을 다시 보내달라는 요청에 DS 사슬을 다시 돌리지 않아도 된다.

관점 라벨과 성향, 요약은 DS2 가 계산해 ds_output 에 JSONL 로 둔다. 있으면 붙이고 없으면
비워 둔다. 비어 있으면 발행기가 목업으로 채울지 고르게 된다.

DS gold 와 ds_output 은 로컬 경로다. DS 코드가 HDFS 를 쓰지 못해 그대로 두고 읽기
전용으로 붙인다.

  spark-submit --master local[*] jobs/gold_issue_feed.py            # 오늘(KST), 가장 늦은 창
  spark-submit --master local[*] jobs/gold_issue_feed.py 2026-09-08 --window 2026-09-07
"""

import argparse
import datetime as dt
import glob
import logging
import os

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

import metrics

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


def ds2_file_for(window, ds_gold=None, ds_output=None):
    """창과 짝인 DS2 파일 하나. 없으면 None.

    이슈 번호는 창마다 다시 배정되므로 다른 창을 본 DS2 결과는 붙지 않는다. 짝은
    시각으로 본다 — 창 폴더가 마지막으로 쓰인 뒤에 만들어진 가장 최근 파일이다. 사슬이
    같은 창을 다시 쓰면 폴더 시각이 앞서 나가고 옛 DS2 파일은 자연히 걸러진다.

    ds_output 의 모든 파일을 읽던 때는 6일치 옛 기사 1만 4천 건이 "우리 표에 없음"
    경고에 찍혀 실제 어긋남이 묻혔다 (2026-09-16 실측). DS2 가 파일 이름을 창 이름으로
    맞춰 주면 이름으로 바꾼다.
    """
    ds_gold = ds_gold or DS_GOLD
    ds_output = ds_output or DS_OUTPUT
    marker = os.path.join(ds_gold, "issue_summary", f"window_start={window}")
    # 폴더와 그 안 parquet 중 늦은 시각. Spark 는 덮어쓸 때 파일을 지우고 새로 만들어
    # 폴더 시각도 따라가지만, 어느 쪽이 갱신되든 잡히게 둘 다 본다
    since = max([os.path.getmtime(marker)] +
                [os.path.getmtime(f) for f in glob.glob(os.path.join(marker, "*"))])         if os.path.isdir(marker) else 0
    candidates = sorted(
        (os.path.getmtime(path), path)
        for path in glob.glob(os.path.join(ds_output, "*.jsonl"))
        if os.path.getmtime(path) >= since)
    return candidates[-1][1] if candidates else None


def _blank_to_null(col):
    """빈 문자열을 결측으로 본다.

    coalesce 는 null 만 뒤 값으로 바꾼다. DS2 가 commonFactsBriefing 을 "" 로 주면 그게
    값이 있는 것으로 보여 대표 기사 본문으로 채우는 길이 막혔고, 발행기에서 이슈 178개가
    필수 필드 비움으로 잡혔다 (2026-09-16 실측). 계약은 "값이 비어 있으면 그 자리는
    비운 채" 이므로 "" 도 비어 있는 것으로 흡수한다.
    """
    return F.when(F.trim(col) == "", None).otherwise(col)


def read_ds2(spark, window):
    """창과 짝인 DS2 결과를 기사당 한 줄로 펼쳐 읽는다. 짝인 파일이 없으면 None.

    DS2 는 BE 스펙 모양의 JSONL 을 둔다. 이슈 하나가 한 줄이고 기사가 배열이라, 붙이려면
    배열을 펼쳐야 한다. 붙이는 키는 clusterId 와 link 다.
    """
    path = ds2_file_for(window)
    if path is None:
        logger.info("창 %s 과 짝인 DS2 파일이 없어 관점 값을 비워 둔다: %s", window, DS_OUTPUT)
        return None
    logger.info("DS2 파일 %s", os.path.basename(path))
    raw = spark.read.json(f"file://{path}")
    article = F.explode("articles").alias("article")
    return (raw.select(F.col("clusterId").alias("cluster_id"),
                       _blank_to_null(F.col("factSummary")).alias("ds2_fact_summary"),
                       _blank_to_null(F.col("commonFactsBriefing")).alias("ds2_briefing"),
                       _blank_to_null(F.col("category")).alias("ds2_category"), article)
            .select("cluster_id", "ds2_fact_summary", "ds2_briefing", "ds2_category",
                    F.col("article.link").alias("link"),
                    _blank_to_null(F.col("article.viewpointGroupLabel")).alias("ds2_label"),
                    _blank_to_null(F.col("article.stance")).alias("ds2_stance"))
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


def latest_window(spark):
    """DS 산출물에 있는 가장 늦은 창."""
    summary = spark.read.parquet(f"file://{DS_GOLD}/issue_summary")
    return str(summary.agg(F.max("window_start")).collect()[0][0])


def build(spark, day, window=None):
    """DS 표 셋을 합쳐 기사당 한 줄인 표를 만들고 DS2 분석 값을 붙인다.

    window 는 DS 산출물의 창이고, 생략하면 가장 늦은 창을 쓴다.
    """
    summary = spark.read.parquet(f"file://{DS_GOLD}/issue_summary")
    registry = spark.read.parquet(f"file://{DS_GOLD}/issue_registry")
    articles = spark.read.parquet(f"file://{DS_GOLD}/articles")

    # 관점 분석 대상 기사만 담는다 — DS2(export_ds2_jsonl.py)와 같은 두 조건이다.
    # 표 형식(structured) 기사와 정제 본문이 빈 기사는 DS2 가 관점을 계산하지 않아 gold 에
    # 넣으면 관점 값이 null 로 남고 BE 필수 필드 점검에서 걸린다 (2026-09-16 실측 244건,
    # 이슈 15개는 통째로). 발행 대상 = 관점 분석 대상으로 기준을 맞춘다.
    # structured 가 null 이면 DS2 처럼 표 형식으로 본다
    analyzable = (
        spark.read.parquet(f"file://{DS_GOLD}/issue_quality")
        .where(~F.coalesce(F.col("structured"), F.lit(True)))
        .select("article_id")
        .join(spark.read.parquet(f"file://{DS_GOLD}/clean")
              .where(F.trim(F.coalesce(F.col("content_clean"), F.lit(""))) != "")
              .select("article_id"), "article_id")
        .distinct())
    registry = registry.join(analyzable, "article_id")

    # 이슈 번호는 창마다 다시 배정된다 — 같은 번호가 창에 따라 다른 사건을 가리키므로
    # 창을 섞으면 이슈에 딴 기사가 붙는다. 창 하나를 통째로 쓴다. 실측으로 섞었을 때
    # DS2 가 48% 만 붙었고 창을 맞추면 99% 붙었다
    window = window or latest_window(spark)
    picked = F.col("window_start") == F.lit(window).cast("date")
    summary, registry = summary.where(picked), registry.where(picked)
    if summary.rdd.isEmpty():
        # 빈 표로 gold 를 덮으면 이미 발행한 이슈가 사라진다
        raise SystemExit(f"DS 산출물에 창 {window} 이 없다")
    if registry.rdd.isEmpty():
        raise SystemExit(f"창 {window} 에 관점 분석 대상 기사가 없다")
    logger.info("DS 창 %s", window)

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


def build_with_ds2(spark, day, window):
    return merge_ds2(build(spark, day, window), read_ds2(spark, window))


def write(df, day, window=None):
    (df.repartition(1)  # 하루 분량이 1MB 남짓이라 파일 하나로 충분하다
       .write.mode("overwrite")
       .option("partitionOverwriteMode", "dynamic")
       .partitionBy("dt").parquet(GOLD))
    issues, rows = df.select("cluster_id").distinct().count(), df.count()
    logger.info("gold 이슈 피드 %s: 이슈 %s개, 기사 %s건", day, f"{issues:,}", f"{rows:,}")
    # 관점 값이 붙은 기사 수. rows 로 나누면 DS2 연결 비율이 된다. 창이 어긋나면
    # 이 값이 0 에 가까워진다 (S15P21E105-79)
    metrics.push("gold_issue_feed", lambda: [
        metrics.line("gold_issues", issues),
        metrics.line("gold_articles", rows),
        metrics.line("gold_ds2_matched_rows", df.where(F.col("stance").isNotNull()).count()),
        metrics.line("gold_window", 1, {"window": window or ""}),
    ])


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("day", nargs="?", help="쌓을 날짜. 생략하면 오늘(KST)")
    ap.add_argument("--window", help="쓸 DS 창. 생략하면 가장 늦은 창")
    args = ap.parse_args()
    day = args.day or today_kst()

    spark = (SparkSession.builder.appName("gold_issue_feed")
             .config("spark.locality.wait", "0")  # bronze_to_silver 와 같은 이유
             .getOrCreate())
    try:
        window = args.window or latest_window(spark)
        write(build_with_ds2(spark, day, window), day, window)
    finally:
        spark.stop()
