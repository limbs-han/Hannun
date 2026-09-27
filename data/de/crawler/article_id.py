"""기사 고유 식별자 생성 (article_v1 계약, S15P21E105-55).

article_id = "sha256:" + SHA-256(publisher_id + "|" + 정규화된 link) 소문자 hex.
정규화 규칙은 schemas/article_v1.json 의 article_id 설명과 반드시 일치해야 한다:
프래그먼트 제거, 추적 파라미터 제거, 남은 쿼리 파라미터 정렬.
쿼리스트링을 통째로 제거하면 안 된다 — KBS·SBS·오마이뉴스는 기사 ID 가 쿼리에
있어, 실측에서 220만 건이 언론사당 ID 1개로 붕괴했다.

Kafka 발행 key(pipeline)와 적재 변환의 article_id 필드가 같은 값을 갖도록
이 모듈 하나만 쓴다.
"""

import hashlib
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "igshid", "page", "date", "ref", "from",
}


def normalize_link(link):
    """프래그먼트·추적 파라미터를 제거하고 남은 쿼리를 정렬한 URL 을 돌려준다."""
    parts = urlsplit(link.strip())
    params = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k not in TRACKING_PARAMS
    ]
    query = urlencode(sorted(params))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, ""))


def article_id(publisher_id, link):
    raw = f"{publisher_id}|{normalize_link(link)}"
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()
