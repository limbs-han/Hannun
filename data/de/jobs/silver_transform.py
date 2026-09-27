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


# 카테고리 표준 이름 (S15P21E105-68).
#
# 과거 데이터셋에는 서로 다른 category 값이 2,253 개 있다. 사회·사회일반·지역·전국이
# 따로 세어지고 경제·증권·부동산·경제일반이 흩어져 있어 그대로는 화면에서 목록을 나눌 수
# 없다. 상위 값을 아홉 개로 합치고 **표에 없는 값은 원문 그대로 둔다** — 지역 방송
# 프로그램명이 꼬리에 2천 개 넘게 있어 다 옮길 수 없고, 억지로 OTHER 로 보내면 정보가
# 사라진다. 상위 60 개가 전체의 89% 다.
#
# 실시간 수집분은 섹션 피드 이름이 이미 표준값이라 이 표를 그냥 통과한다.
_CATEGORY_ALIAS = {
    "증권": "경제", "부동산": "경제", "금융": "경제",
    "지역": "사회", "전국": "사회", "지방": "사회", "교육": "사회",
    "대전세종충청": "사회", "검찰・법원": "사회", "사건": "사회",
    "지구촌뉴스": "국제",
    "생활문화": "문화", "생활": "문화",
    "서경스타": "연예", "스타": "연예",
    "IT": "IT과학", "IT과학": "IT과학", "IT의학": "IT과학", "과학": "IT과학",
}

# 분야가 아닌 값. 계약대로 결측(OTHER)으로 보낸다
_NOT_A_CATEGORY = {"최신기사", "오피니언", "미분류", "일반", "사설칼럼", "연합뉴스",
                   "전체", "헤드라인", "종합"}

# 값을 쪼개는 구분자. "경제 · 금융" 은 첫 조각을 쓰고 "IT_과학" 은 붙여서 본다
_SPLIT = ("·", "・", "/", ".", "|", ">", "-", "_")

_STANDARD = {"정치", "경제", "사회", "국제", "문화", "스포츠", "연예", "IT과학", "산업"}


def normalize_category(value):
    """카테고리 값을 표준 이름으로 맞춘다. 표에 없으면 원문을 그대로 돌려준다."""
    if not value:
        return None
    raw = value.strip()
    if not raw:
        return None

    # 구분자로 나눈 첫 조각과 구분자를 지운 형태를 함께 본다
    joined = raw
    first = raw
    for sep in _SPLIT:
        joined = joined.replace(sep, "")
        if sep in first:
            first = first.split(sep)[0]
    for form in (raw, first.strip(), joined.replace(" ", "")):
        head = form[:-2] if form.endswith("일반") and len(form) > 2 else form
        for candidate in (form, head):
            if candidate in _NOT_A_CATEGORY:
                return "OTHER"
            if candidate in _STANDARD:
                return candidate
            found = _CATEGORY_ALIAS.get(candidate)
            if found:
                return found
    return raw


# 기사 주소 경로에서 카테고리를 읽는 표 (S15P21E105-68).
#
# 섹션 피드를 쓰기 전(2026-09-11)에 모인 실시간 기사 3만 5천 건이 카테고리 없이 쌓였다.
# 다섯 언론사는 주소 경로에 분야가 들어 있어 되살릴 수 있다. 나머지 여덟 곳은 기사 번호만
# 있어 본문을 다시 긁어야 하고, 그 값어치가 열 시간 재수집에 못 미쳐 비워 둔다.
#
# 앞으로도 쓰인다. 연합뉴스와 조선일보는 IT과학 섹션 피드가 없어 그 분야가 비는데,
# 조선일보는 주소로 메꿔진다.
_LINK_CATEGORY = {
    "politics": "정치", "congress": "정치", "president": "정치", "diplomacy": "정치",
    "bluehouse": "정치",
    "economy": "경제", "business": "경제", "stock": "경제", "finance": "경제",
    "securities": "경제", "realestate": "경제", "estate": "경제", "industry": "경제",
    "weeklybiz": "경제", "biznews": "경제", "car": "경제",
    "society": "사회", "national": "사회", "accident": "사회", "law": "사회",
    "area": "사회", "capital": "사회", "environment": "사회", "people": "사회",
    "peoples": "사회",
    "international": "국제", "inter": "국제", "world": "국제", "america": "국제",
    "culture": "문화", "culture-life": "문화", "life": "문화", "book": "문화",
    "sports": "스포츠", "sport": "스포츠", "baseball": "스포츠", "golf": "스포츠",
    "entertainment": "연예", "starintern": "연예",
    "it": "IT과학", "science": "IT과학",
}

# 한겨레는 society_general 처럼 뒤에 붙여 세분한다. 앞부분만 떼어 같은 표로 찾는다
_GENERAL = ("_general", "-general")

_PATH_WORD = re.compile(r"/([A-Za-z][A-Za-z_-]{1,24})(?=/)")


def category_from_link(link):
    """기사 주소 경로에서 카테고리를 읽는다. 못 찾으면 None.

    경로 낱말을 앞에서부터 보고 표에 있는 첫 값을 쓴다. news·article·all 처럼 분야가
    아닌 낱말은 표에 없어 그냥 지나간다.
    """
    if not link:
        return None
    path = link.split("//", 1)[-1]
    path = path[path.index("/"):] if "/" in path else ""
    for word in _PATH_WORD.findall(path):
        word = word.lower()
        for tail in _GENERAL:
            if word.endswith(tail):
                word = word[: -len(tail)]
                break
        found = _LINK_CATEGORY.get(word)
        if found:
            return found
    return None


def resolve_category(value, link):
    """카테고리를 정한다. 표준 이름으로 맞추고, 비거나 OTHER 면 주소에서 읽는다.

    OTHER 를 결측과 같이 보는 이유: 데이터셋 원본에 OTHER 가 들어 있거나 이전 적재가
    OTHER 로 채운 값을 다시 읽을 때, 주소에서 읽을 수 있는데도 그냥 넘기면 안 된다.
    """
    found = normalize_category(value)
    if not found or found == "OTHER":
        found = category_from_link(link)
    return found or "OTHER"


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
        # 피드가 카테고리를 안 줬으면 주소 경로에서 읽어 본다 (S15P21E105-68)
        # 값을 표준 이름으로 맞추고, 없거나 OTHER 면 주소 경로에서 읽어 본다
        "category": resolve_category(category, link),
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
