import urllib.robotparser

from crawler.article_id import article_id
from crawler.pipeline import run
from crawler.politeness import RateLimiter, RobotsGate
from tests.test_extractor import ARTICLE_HTML


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.slept = []

    def clock(self):
        return self.now

    def sleep(self, sec):
        self.slept.append(sec)
        self.now += sec


def test_rate_limiter_waits_per_domain():
    fake = FakeClock()
    limiter = RateLimiter(interval=1.0, clock=fake.clock, sleep=fake.sleep)

    limiter.wait("https://a.test/1")      # 첫 요청은 대기 없음
    assert fake.slept == []

    limiter.wait("https://a.test/2")      # 같은 도메인 즉시 재요청 → 1초 대기
    assert len(fake.slept) == 1 and fake.slept[0] > 0.9

    limiter.wait("https://b.test/1")      # 다른 도메인은 대기 없음
    assert len(fake.slept) == 1

    fake.now += 5.0
    limiter.wait("https://a.test/3")      # 간격이 지났으면 대기 없음
    assert len(fake.slept) == 1


def test_robots_gate_blocks_disallowed():
    gate = RobotsGate("HannunBot")
    parser = urllib.robotparser.RobotFileParser()
    parser.parse("User-agent: *\nDisallow: /private/".splitlines())
    gate._parsers["news.test"] = parser  # 네트워크 대신 캐시에 직접 주입

    assert gate.allowed("https://news.test/article/1") is True
    assert gate.allowed("https://news.test/private/1") is False


RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>테스트 피드</title>
<item><title>죽는 기사</title><link>https://news.test/boom</link>
<pubDate>Wed, 26 Aug 2026 05:30:00 GMT</pubDate></item>
<item><title>사는 기사</title><link>https://news.test/ok</link>
<pubDate>Wed, 26 Aug 2026 05:31:00 GMT</pubDate></item>
</channel></rss>"""

FEEDS = [{"company": "테스트", "publisher_id": "test", "rss": [RSS_XML]}]


class AllowAll:
    def allowed(self, url):
        return True


class NoWait:
    def wait(self, url):
        pass


class FakeProducer:
    def __init__(self):
        self.keys = []

    def produce(self, topic, key, value, on_delivery=None):
        self.keys.append(key)

    def poll(self, timeout):
        pass

    def flush(self):
        pass


def _fetch(url):
    if url.endswith("/boom"):
        raise RuntimeError("연결 실패")
    return ARTICLE_HTML


def test_article_failure_is_isolated(tmp_path):
    producer = FakeProducer()
    sent, skipped = run(
        tmp_path / "seen.sqlite",
        producer=producer,
        fetch_fn=_fetch,
        feeds=FEEDS,
        limiter=NoWait(),
        robots=AllowAll(),
    )
    assert (sent, skipped) == (1, 1)  # 한 기사가 죽어도 나머지는 발행
    assert producer.keys == [article_id("test", "https://news.test/ok")]
