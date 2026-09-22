from crawler.extractor import parse

BODY = "정부는 오늘 새로운 청년 지원 정책을 발표했다. 이번 정책은 청년 주거 안정과 취업 지원을 핵심으로 한다. " * 5

ARTICLE_HTML = f"""<!DOCTYPE html>
<html><head>
<title>정부, 새로운 청년 정책 발표</title>
<meta property="article:published_time" content="2026-08-27T10:00:00+09:00">
</head><body>
<span itemprop="author">홍길동</span>
<article>
<h1>정부, 새로운 청년 정책 발표</h1>
<p>{BODY}</p>
<p>{BODY}</p>
</article>
</body></html>"""

SHORT_HTML = """<!DOCTYPE html>
<html><head><title>짧은 글</title></head>
<body><article><p>백 자가 안 되는 본문.</p></article></body></html>"""


def test_parse_article():
    parsed = parse(ARTICLE_HTML, url="https://news.test/a/1")
    assert parsed is not None
    assert "청년 지원 정책" in parsed["article"]
    assert len(parsed["article"]) >= 100
    assert parsed["reporter"] == "홍길동"
    assert parsed["published"].startswith("2026-08-27")


def test_parse_rejects_short_and_empty():
    assert parse(SHORT_HTML, url="https://news.test/a/2") is None
    assert parse(None) is None
    assert parse("") is None
