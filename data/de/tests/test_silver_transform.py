import json
import os

import pytest
from jsonschema import Draft7Validator

import backfill.bigkinds as bigkinds
from crawler.feeds import FEEDS
from crawler.publishers import PUBLISHER_ID
from jobs import silver_transform as st

with open(os.path.join(os.path.dirname(__file__), "..", "schemas", "article_v1.json"), encoding="utf-8") as f:
    VALIDATOR = Draft7Validator(json.load(f))


def _assert_v1(record):
    contract = {k: v for k, v in record.items() if k != "dt"}
    assert list(VALIDATOR.iter_errors(contract)) == []


def test_publisher_map_agrees_with_feeds_and_bigkinds():
    for feed in FEEDS:
        assert PUBLISHER_ID[feed["company"]] == feed["publisher_id"]
    for company, pid in bigkinds.PUBLISHER_ID.items():
        assert PUBLISHER_ID[company] == pid
    assert PUBLISHER_ID["한겨례"] == PUBLISHER_ID["한겨레"] == "hani"  # 데이터셋 오타 표기


def test_dataset_row_becomes_valid_v1_in_utc_with_kst_partition():
    row = ["동아일보", "제목 amp;#39;인용amp;#39;", "https://a.com/기사?x=1", "2020-01-01 00:30",
           "", "", "동아일보", "본문 &amp;quot;끝&amp;quot;"]
    record = st.from_dataset_row(row, "2026-09-07T01:00:00Z")
    _assert_v1(record)
    assert record["published"] == "2019-12-31T15:30:00Z"  # KST 00:30 → UTC 전날
    assert record["dt"] == "2020-01-01"                    # 파티션은 한국 날짜
    assert record["title"] == "제목 '인용'"
    assert record["article"] == '본문 "끝"'
    assert record["category"] == "OTHER"
    assert record["reporter"] is None
    assert record["link"] == "https://a.com/%EA%B8%B0%EC%82%AC?x=1"
    assert record["source_type"] == "DATASET"
    assert record["publisher_id"] == "donga"


def test_dataset_row_reads_korean_ampm_and_drops_unparsable_time():
    base = ["KBS뉴스", "제목", "https://news.kbs.co.kr/news/view.do?ncd=1", None, "", "", "", "본문"]
    for raw, expected in [("2023-01-01 오후 9:40:00", "2023-01-01T12:40:00Z"),
                          ("2023-01-01 오전 12:05:00", "2022-12-31T15:05:00Z"),
                          ("2023-01-01 오후 12:05", "2023-01-01T03:05:00Z"),
                          ("2023-01-01 09:40:00", "2023-01-01T00:40:00Z"),
                          ("2023.06.23 10:40", "2023-06-23T01:40:00Z")]:
        row = base[:3] + [raw] + base[4:]
        assert st.from_dataset_row(row, "x")["published"] == expected, raw
    assert st.from_dataset_row(base[:3] + ["2023-01-01 밤 9시"] + base[4:], "x") is None


def test_dataset_row_rejects_bad_rows():
    assert st.from_dataset_row(["동아일보", "제목", "https://a.com/1", "2020-01-01 00:30", "", "", "", ""], "x") is None
    assert st.from_dataset_row(["동아일보", "제목", "not-a-url", "2020-01-01 00:30", "", "", "", "본문"], "x") is None
    assert st.from_dataset_row(["동아일보", "제목"], "x") is None
    assert st.from_dataset_row(None, "x") is None


def test_realtime_message_becomes_valid_v1():
    value = json.dumps({
        "company": "연합뉴스", "title": "t", "link": "https://www.yna.co.kr/view/AKR1",
        "published": "2026-09-06T16:40:02+09:00", "category": None, "category_str": None,
        "reporter": "박원희", "thumbnail_url": "https://img.yna.co.kr/a.jpg", "article": "본문 " * 30,
    }, ensure_ascii=False)
    record = st.from_realtime_message(value, "2026-09-06")
    _assert_v1(record)
    assert record["published"] == "2026-09-06T07:40:02Z"
    assert record["dt"] == "2026-09-06"
    assert record["crawled_at"] == "2026-09-06T00:00:00Z"
    assert record["category"] == "OTHER"
    assert record["source_type"] == "RSS"
    assert record["publisher_id"] == "yonhap"


def test_realtime_message_without_body_or_broken_json_is_dropped():
    meta_only = json.dumps({"company": "연합뉴스", "title": "t", "link": "https://a", "published": "2026-09-06T16:40:02+09:00"})
    assert st.from_realtime_message(meta_only, "2026-09-06") is None
    assert st.from_realtime_message("{not json", "2026-09-06") is None


def test_unknown_company_raises_typed_error_with_name():
    value = json.dumps({"company": "LOADTEST", "title": "t", "link": "https://a", "published": "2026-09-06T16:40:02+09:00", "article": "본문"})
    with pytest.raises(st.UnknownPublisher) as caught:  # 잡은 이 예외를 잡아 행만 건너뛰고 이름별로 센다
        st.from_realtime_message(value, "2026-09-06")
    assert caught.value.args[0] == "LOADTEST"


def test_bigkinds_line_passes_through_with_partition():
    record = {
        "company": "경향신문", "title": "t", "link": "https://www.khan.co.kr/article/1",
        "published": "2024-07-01T14:59:59Z", "category": "정치", "category_str": "정치>행정",
        "reporter": None, "article": "본문", "schema_version": "1.0",
        "article_id": "sha256:" + "0" * 64, "publisher_id": "khan", "source_type": "DATASET",
        "language": "ko", "thumbnail_url": None, "crawled_at": "2026-09-02T00:00:00Z",
    }
    out = st.from_bigkinds_line(json.dumps(record))
    _assert_v1(out)
    assert out["dt"] == "2024-07-01"  # UTC 14:59 → KST 23:59 같은 날
    assert st.from_bigkinds_line(json.dumps({**record, "article": ""})) is None


def test_normalize_category_merges_variants():
    """흩어진 표기를 표준 아홉 개로 모은다 (S15P21E105-68)."""
    assert st.normalize_category("사회일반") == "사회"
    assert st.normalize_category("정치일반") == "정치"
    assert st.normalize_category("증권") == "경제"
    assert st.normalize_category("금융/증권") == "경제"
    assert st.normalize_category("경제 · 금융") == "경제"
    assert st.normalize_category("지역") == "사회"
    assert st.normalize_category("IT_과학") == "IT과학"
    assert st.normalize_category("IT·과학") == "IT과학"
    assert st.normalize_category("서경스타") == "연예"
    # 산업은 실시간 섹션 피드에 있는 표준값이라 경제로 합치지 않는다
    assert st.normalize_category("산업") == "산업"


def test_normalize_category_drops_non_categories():
    """분야가 아닌 값은 계약대로 결측으로 보낸다."""
    for value in ("최신기사", "오피니언", "미분류", "일반", "사설.칼럼", "연합뉴스"):
        assert st.normalize_category(value) == "OTHER", value


def test_normalize_category_keeps_unknown_as_is():
    """표에 없는 값은 원문을 지킨다.

    과거 데이터셋에 서로 다른 값이 2,253 개 있고 꼬리는 대부분 지역 방송 프로그램명이다.
    억지로 OTHER 로 보내면 정보가 사라진다.
    """
    assert st.normalize_category("뉴스 9") == "뉴스 9"
    assert st.normalize_category("930뉴스") == "930뉴스"
    assert st.normalize_category(None) is None
    assert st.normalize_category("   ") is None


def test_category_from_link_reads_path():
    """주소 경로에 분야가 있는 다섯 언론사는 카테고리를 되살린다 (S15P21E105-68)."""
    assert st.category_from_link(
        "https://www.donga.com/news/Inter/article/all/1/2/3") == "국제"
    assert st.category_from_link(
        "https://www.hani.co.kr/arti/society/society_general/1.html") == "사회"
    assert st.category_from_link("https://www.mk.co.kr/news/stock/1") == "경제"
    assert st.category_from_link(
        "https://www.seoul.co.kr/news/international/2026/09/02/1") == "국제"
    assert st.category_from_link(
        "https://www.chosun.com/culture-life/book/2026/09/01/X") == "문화"


def test_category_from_link_gives_up_on_numeric_paths():
    """기사 번호만 있는 여덟 언론사는 못 읽는다. 본문 재수집이 유일한 길이라 비워 둔다."""
    for link in ("https://www.yna.co.kr/view/AKR1",
                 "https://www.kmib.co.kr/article/view.asp?arcid=1",
                 "https://www.etnews.com/20260901000259",
                 "https://news.sbs.co.kr/news/endPage.do?news_id=N1",
                 "", None):
        assert st.category_from_link(link) is None, link


def test_resolve_category_falls_back_to_link():
    """OTHER 는 결측과 같이 본다 (S15P21E105-68).

    이전 적재가 OTHER 로 채운 값을 다시 읽을 때 주소에서 읽을 수 있으면 되살려야 한다.
    실측으로 이미 쌓인 실시간 기사 3만 5천 건 중 30.7% 가 이 규칙으로 채워졌다.
    """
    link = "https://www.mk.co.kr/news/society/1"
    assert st.resolve_category("OTHER", link) == "사회"
    assert st.resolve_category(None, link) == "사회"
    assert st.resolve_category("", link) == "사회"
    # 값이 있으면 주소보다 값이 먼저다
    assert st.resolve_category("정치", link) == "정치"
    # 둘 다 없으면 OTHER
    assert st.resolve_category(None, "https://www.yna.co.kr/view/AKR1") == "OTHER"
