from crawler.rss_collector import collect_new

RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>테스트 피드</title>
<item><title>첫 기사</title><link>https://news.test/a/1</link>
<pubDate>Wed, 20 Aug 2026 05:30:00 GMT</pubDate></item>
<item><title>둘째 기사</title><link>https://news.test/a/2</link></item>
</channel></rss>"""

FEEDS = [{"company": "테스트", "publisher_id": "test", "rss": {"정치": RSS_XML}}]


def test_collect_and_dedup(tmp_path):
    db = tmp_path / "seen.sqlite"

    items = {i["link"]: i for i in collect_new(db, feeds=FEEDS)}
    assert len(items) == 2

    first = items["https://news.test/a/1"]
    assert first["company"] == "테스트"
    assert first["publisher_id"] == "test"
    assert first["title"] == "첫 기사"
    assert first["published"] == "2026-08-20 14:30:00"  # UTC 05:30 → KST 14:30

    assert items["https://news.test/a/2"]["published"] is None

    # 같은 피드를 다시 훑으면 전부 이미 본 기사라 빈 목록
    assert collect_new(db, feeds=FEEDS) == []


def test_encode_link_is_idempotent_and_targets_hangul_space_only():
    from crawler.rss_collector import encode_link

    raw = "https://a.com/기사 목록?p=1&q=값"
    encoded = encode_link(raw)
    assert encoded == "https://a.com/%EA%B8%B0%EC%82%AC%20%EB%AA%A9%EB%A1%9D?p=1&q=%EA%B0%92"
    assert encode_link(encoded) == encoded  # 멱등
    assert encoded.isascii()
