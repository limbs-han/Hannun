from crawler.rss_collector import collect_new

RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>테스트 피드</title>
<item><title>첫 기사</title><link>https://news.test/a/1</link>
<pubDate>Wed, 20 Aug 2026 05:30:00 GMT</pubDate></item>
<item><title>둘째 기사</title><link>https://news.test/a/2</link></item>
</channel></rss>"""

FEEDS = [{"company": "테스트", "publisher_id": "test", "rss": [RSS_XML]}]


def test_collect_and_dedup(tmp_path):
    db = tmp_path / "seen.sqlite"

    items = {i["link"]: i for i in collect_new(db, feeds=FEEDS)}
    assert len(items) == 2

    first = items["https://news.test/a/1"]
    assert first["company"] == "테스트"
    assert first["title"] == "첫 기사"
    assert first["published"] == "2026-08-20 14:30:00"  # UTC 05:30 → KST 14:30

    assert items["https://news.test/a/2"]["published"] is None

    # 같은 피드를 다시 훑으면 전부 이미 본 기사라 빈 목록
    assert collect_new(db, feeds=FEEDS) == []
