"""기사 본문 추출기 (S15P21E105-62).

기사 URL 의 HTML 에서 본문·기자명·발행시각을 뽑는다. fetch 와 parse 를 분리해서
parse 는 네트워크 없이 테스트할 수 있다.
"""

import json

import trafilatura

MIN_CONTENT_LEN = 100


def fetch(url):
    """URL 의 HTML 을 가져온다. 실패하면 None."""
    return trafilatura.fetch_url(url)


def parse(html, url=None):
    """HTML 에서 {article, reporter, published} 를 뽑는다.

    본문이 없거나 100자 미만이면 None. published 는 페이지 메타데이터 기준이라
    날짜 단위 정밀도일 수 있고, RSS pubDate 가 있으면 그쪽을 우선해야 한다.
    """
    if not html:
        return None
    raw = trafilatura.extract(html, url=url, output_format="json", with_metadata=True)
    if not raw:
        return None
    doc = json.loads(raw)
    article = (doc.get("text") or "").strip()
    if len(article) < MIN_CONTENT_LEN:
        return None
    published = doc.get("date") or None
    if published and len(published) == 10:  # YYYY-MM-DD 만 오면 시각은 자정으로
        published = published + " 00:00:00"
    return {
        "article": article,
        "reporter": doc.get("author") or None,
        "published": published,
    }
