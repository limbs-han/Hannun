"""bronze 세 소스의 한 행을 article_v1 레코드로 바꾸는 순수 함수 (S15P21E105-68).

Spark 없이 테스트할 수 있게 행 단위 함수만 둔다. bronze_to_silver 잡이 RDD map 으로
호출한다. 결과 dict 에는 계약 15필드 외에 파티션용 dt(published 의 한국 날짜)가 붙는다.
"""

import datetime as dt
import json

from backfill.dataset_sender import build_message, clean_text
from crawler.article_id import article_id
from crawler.publishers import PUBLISHER_ID

KST = dt.timezone(dt.timedelta(hours=9))
UTC = dt.timezone.utc

FIELDS = [
    "company", "title", "link", "published", "category", "category_str", "reporter",
    "article", "schema_version", "article_id", "publisher_id", "source_type", "language",
    "thumbnail_url", "crawled_at", "dt",
]
NULLABLE = {"category_str", "reporter", "thumbnail_url"}


def kst_to_utc_z(value):
    """KST 시각 문자열('YYYY-MM-DDTHH:MM:SS+09:00' 또는 타임존 없는 KST) → UTC Z."""
    parsed = dt.datetime.fromisoformat(value.strip().replace(" ", "T"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=KST)
    return parsed.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def kst_date(utc_z):
    """UTC Z 문자열의 한국 날짜. dt 파티션 값이다 (분석 단위가 한국 하루)."""
    parsed = dt.datetime.strptime(utc_z, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    return parsed.astimezone(KST).strftime("%Y-%m-%d")


def _record(company, title, link, published_utc, category, category_str, reporter, article,
            source_type, thumbnail_url, crawled_at):
    # 미등록 언론사는 KeyError 로 잡 전체를 멈춘다. 조용히 넘기면 article_id 가 틀어진다
    publisher_id = PUBLISHER_ID[company]
    return {
        "company": company,
        "title": title,
        "link": link,
        "published": published_utc,
        "category": category or "OTHER",
        "category_str": category_str or None,
        "reporter": reporter or None,
        "article": article,
        "schema_version": "1.0",
        "article_id": article_id(publisher_id, link),
        "publisher_id": publisher_id,
        "source_type": source_type,
        "language": "ko",
        "thumbnail_url": thumbnail_url or None,
        "crawled_at": crawled_at,
        "dt": kst_date(published_utc),
    }


def from_dataset_row(row, crawled_at):
    """데이터셋 CSV 8필드 행 → article_v1. 부적합 행(필드 수·URL·본문 없음)은 None."""
    if row is None or len(row) != 8:
        return None
    row = ["" if v is None else v for v in row]
    message = build_message(row)  # 송신기와 같은 정제 규칙(엔티티 복원·기자명·카테고리)
    article = clean_text(row[7])
    if message is None or not article:
        return None
    return _record(
        message["company"], message["title"], message["link"], kst_to_utc_z(message["published"]),
        message["category"], message["category_str"], message["reporter"], article,
        "DATASET", None, crawled_at,
    )


def from_realtime_message(value, ingest_date):
    """bronze/news 한 줄(Kafka value JSON) → article_v1. 본문 없는 메시지는 None."""
    try:
        msg = json.loads(value)
    except ValueError:
        return None
    article = (msg.get("article") or "").strip()
    if not (article and msg.get("company") and msg.get("title") and msg.get("link")
            and msg.get("published")):
        return None
    return _record(
        msg["company"], msg["title"], msg["link"], kst_to_utc_z(msg["published"]),
        msg.get("category"), msg.get("category_str"), msg.get("reporter"), article,
        "RSS", msg.get("thumbnail_url"),
        # 메시지에 수집 시각이 없어 적재일 자정으로 근사 (2026-09-07 결정)
        f"{ingest_date}T00:00:00Z",
    )


def from_bigkinds_line(value):
    """bronze/bigkinds 한 줄. 이미 article_v1 이라 dt 만 붙인다."""
    record = json.loads(value)
    if not record.get("article"):
        return None
    record["dt"] = kst_date(record["published"])
    return record
