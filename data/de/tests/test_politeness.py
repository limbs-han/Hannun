import urllib.error
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

FEEDS = [{"company": "테스트", "publisher_id": "test", "rss": {"정치": RSS_XML}}]


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


class FlakyRules:
    """앞 fail_count 회는 403, 그 뒤로는 규칙 텍스트를 주는 가짜 robots 서버."""

    def __init__(self, fail_count, rules="User-agent: *\nDisallow: /private/"):
        self.fail_count = fail_count
        self.rules = rules
        self.calls = 0

    def __call__(self, domain):
        self.calls += 1
        if self.calls <= self.fail_count:
            raise urllib.error.HTTPError(f"https://{domain}/robots.txt", 403, "Forbidden", None, None)
        return self.rules


def _gate(fetcher):
    gate = RobotsGate("HannunBot", sleep=lambda s: None)
    gate._fetch_rules = fetcher
    return gate


def test_robots_transient_403_recovers_within_retries():
    gate = _gate(FlakyRules(fail_count=1))  # 1회 403 후 정상
    assert gate.allowed("https://news.test/article/1") is True
    assert gate.allowed("https://news.test/private/1") is False


def test_robots_persistent_403_holds_run_without_permanent_ban():
    fetcher = FlakyRules(fail_count=99)  # 계속 403
    gate = _gate(fetcher)
    assert gate.allowed("https://news.test/article/1") is False  # 이번 실행 보류
    calls_after_first = fetcher.calls
    assert gate.allowed("https://news.test/article/2") is False  # 같은 실행에선 재요청 안 함
    assert fetcher.calls == calls_after_first

    fetcher.fail_count = 0  # 다음 실행에서 서버가 정상으로 돌아온 상황
    fresh = _gate(fetcher)
    assert fresh.allowed("https://news.test/article/1") is True  # 영구 차단이 아님


def test_robots_missing_file_means_allow():
    def not_found(domain):
        return None  # 404 등 규칙 없음

    gate = _gate(not_found)
    assert gate.allowed("https://news.test/anything") is True
