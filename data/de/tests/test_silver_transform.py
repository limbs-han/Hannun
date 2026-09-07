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


def test_unknown_company_fails_loudly():
    value = json.dumps({"company": "없는신문", "title": "t", "link": "https://a", "published": "2026-09-06T16:40:02+09:00", "article": "본문"})
    with pytest.raises(KeyError):
        st.from_realtime_message(value, "2026-09-06")


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
