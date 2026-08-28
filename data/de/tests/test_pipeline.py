import json

from crawler.pipeline import run
from tests.test_extractor import ARTICLE_HTML

RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>테스트 피드</title>
<item><title>정부, 새로운 청년 정책 발표</title><link>https://news.test/a/1</link>
<pubDate>Wed, 26 Aug 2026 05:30:00 GMT</pubDate>
<category>정치</category></item>
</channel></rss>"""

FEEDS = [{"company": "테스트", "publisher_id": "test", "rss": [RSS_XML]}]


class FakeProducer:
    def __init__(self):
        self.messages = []

    def produce(self, topic, key, value, on_delivery=None):
        self.messages.append((topic, key, json.loads(value)))

    def poll(self, timeout):
        pass

    def flush(self):
        pass


class AllowAll:
    def allowed(self, url):
        return True


class NoWait:
    def wait(self, url):
        pass


def test_run_publishes_8_field_article(tmp_path):
    producer = FakeProducer()
    sent, skipped = run(
        tmp_path / "seen.sqlite",
        producer=producer,
        fetch_fn=lambda url: ARTICLE_HTML,
        feeds=FEEDS,
        limiter=NoWait(),
        robots=AllowAll(),
    )
    assert (sent, skipped) == (1, 0)

    topic, key, msg = producer.messages[0]
    assert key == "https://news.test/a/1"
    assert set(msg) == {
        "company", "title", "link", "published",
        "category", "category_str", "reporter", "article",
    }
    assert msg["company"] == "테스트"
    assert msg["published"] == "2026-08-26 14:30:00"  # RSS pubDate 가 페이지 날짜보다 우선
    assert msg["category_str"] == "정치"
    assert msg["reporter"] == "홍길동"
    assert len(msg["article"]) >= 100


def test_run_skips_unparsable_page(tmp_path):
    producer = FakeProducer()
    sent, skipped = run(
        tmp_path / "seen.sqlite",
        producer=producer,
        fetch_fn=lambda url: None,
        feeds=FEEDS,
        limiter=NoWait(),
        robots=AllowAll(),
    )
    assert (sent, skipped) == (0, 1)
    assert producer.messages == []
