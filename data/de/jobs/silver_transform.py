"""bronze 세 소스의 한 행을 article_v1 레코드로 바꾸는 순수 함수 (S15P21E105-68).

Spark 없이 테스트할 수 있게 행 단위 함수만 둔다. bronze_to_silver 잡이 RDD map 으로
호출한다. 결과 dict 에는 계약 15필드 외에 파티션용 dt(published 의 한국 날짜)가 붙는다.
"""

import datetime as dt
import json
import re

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


# 데이터셋 실측(2026-09-07): 전 연도에 '오후 9:40:00' 꼴 12시간제 약 18만 건, 2023년에
# '2023.06.23 10:40' 꼴 점 구분 날짜 약 32만 건이 섞여 있다
_DOT_DATE = re.compile(r"^(\d{4})\.(\d{2})\.(\d{2})")
_AMPM = re.compile(r"^(\d{4}-\d{2}-\d{2}) (오전|오후) (\d{1,2}):(\d{2})(?::(\d{2}))?$")


def kst_to_utc_z(value):
    """KST 시각 문자열 → UTC Z. 형식을 못 읽으면 ValueError.

    받는 꼴: 'YYYY-MM-DDTHH:MM:SS+09:00', 'YYYY-MM-DD HH:MM[:SS]', 'YYYY-MM-DD 오전|오후 H:MM[:SS]',
    날짜 구분자가 점인 'YYYY.MM.DD ...'
    """
    value = _DOT_DATE.sub(r"\1-\2-\3", value.strip())
    matched = _AMPM.match(value)
    if matched:
        day, ampm, hour, minute, second = matched.groups()
        hour = int(hour) % 12 + (12 if ampm == "오후" else 0)
        value = f"{day} {hour:02d}:{minute}:{second or '00'}"
    if len(value) == 16:
        value += ":00"
    parsed = dt.datetime.fromisoformat(value.replace(" ", "T"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=KST)
    return parsed.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def kst_date(utc_z):
    """UTC Z 문자열의 한국 날짜. dt 파티션 값이다 (분석 단위가 한국 하루)."""
    parsed = dt.datetime.strptime(utc_z, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    return parsed.astimezone(KST).strftime("%Y-%m-%d")


class UnknownPublisher(KeyError):
    """매핑 표에 없는 언론사. 잡은 이 행만 건너뛰고 언론사별 건수를 따로 집계한다.

    처음엔 잡 전체를 멈추게 했는데, BE 부하테스트 메시지(company=LOADTEST) 222만 건이
    운영 토픽으로 들어온 실측(2026-09-07)이 있어 한 건이 15분 파이프라인을 죽이지 않게 바꿨다.
    """


def _record(company, title, link, published_utc, category, category_str, reporter, article,
            source_type, thumbnail_url, crawled_at):
    publisher_id = PUBLISHER_ID.get(company)
    if publisher_id is None:
        raise UnknownPublisher(company)
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
    try:
        published = kst_to_utc_z(row[3])  # 송신기 가공본 대신 원문을 직접 해석
    except ValueError:
        return None  # 못 읽는 시각은 행만 제외하고 잡은 계속 (제외 건수는 누산기로 집계)
    return _record(
        message["company"], message["title"], message["link"], published,
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
    try:
        published = kst_to_utc_z(msg["published"])
    except ValueError:
        return None
    return _record(
        msg["company"], msg["title"], msg["link"], published,
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
