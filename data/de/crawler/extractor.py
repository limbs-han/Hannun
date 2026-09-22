"""기사 본문 추출기 (S15P21E105-62).

기사 URL 의 HTML 에서 본문·기자명·발행시각을 뽑는다. fetch 와 parse 를 분리해서
parse 는 네트워크 없이 테스트할 수 있다.
"""

import json
import urllib.request

import trafilatura

from crawler.rss_collector import USER_AGENT

MIN_CONTENT_LEN = 100


def fetch(url):
    """URL 의 HTML 을 가져온다. 실패하면 None.

    User-Agent 를 반드시 지정한다. 익명 요청을 거부하는 언론사(세계일보 확인됨)가
    있어서, UA 없이 보내면 요청 자체가 실패한다.

    ponytail: 일부 언론사(연합뉴스 확인됨)는 없는 기사도 HTTP 200 + 안내 페이지로
    응답해서 상태코드로 못 거른다. RSS 가 방금 준 링크는 유효하다는 전제로 두고,
    죽은 링크 감지가 필요해지면 제목 대조 등으로 보강.
    """
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, "ignore")
    except Exception:
        return None


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
        "thumbnail_url": doc.get("image") or None,
    }
