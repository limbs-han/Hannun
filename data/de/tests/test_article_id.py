import re

from crawler.article_id import article_id, normalize_link


def test_format():
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", article_id("test", "https://news.test/a/1"))


def test_tracking_params_and_fragment_ignored():
    # utm·프래그먼트 차이는 같은 기사 — 같은 ID
    a = article_id("hani", "https://news.test/view?b=2&a=1&utm_source=x&fbclid=y#top")
    b = article_id("hani", "https://news.test/view?a=1&b=2")
    assert a == b


def test_article_query_preserved():
    # KBS 처럼 기사 ID 가 쿼리에 있는 URL 은 쿼리를 지우면 안 된다
    a = article_id("kbs", "https://news.kbs.co.kr/news/view.do?ncd=1")
    b = article_id("kbs", "https://news.kbs.co.kr/news/view.do?ncd=2")
    assert a != b


def test_publisher_scopes_id():
    assert article_id("a", "https://news.test/1") != article_id("b", "https://news.test/1")


def test_normalize_sorts_remaining_query():
    assert (normalize_link("https://n.t/v?z=1&a=2&utm_medium=m")
            == "https://n.t/v?a=2&z=1")
