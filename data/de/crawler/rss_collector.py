"""RSS 목록 수집기 (S15P21E105-61).

언론사 RSS 를 1회 훑어 아직 보지 않은 기사만 8필드 명명(company/title/link/published)
으로 돌려준다. 본문 수집과 Kafka 발행은 다음 단계(S15P21E105-62) 몫이다.
"""

import logging
import re
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

import feedparser

from crawler.feeds import FEEDS

logger = logging.getLogger(__name__)

# robotparser 는 UA 의 첫 토큰으로 규칙을 매칭하므로 봇 이름이 앞에 와야 한다
USER_AGENT = "HannunBot/0.1 (+https://lab.ssafy.com/s15-bigdata-dist-sub1/S15P21E105)"

_HANGUL_OR_SPACE = re.compile(r"[ ㄱ-ㆎ가-힣]")


def encode_link(url):
    """link 의 한글·공백만 %XX(UTF-8, 대문자)로 인코딩한다 (팀 확정 규칙).

    수집 시점에 한 번만 적용하고, 이후 Kafka·HDFS·DS·BE 매칭까지 전 구간이
    이 문자열을 변환 없이 그대로 쓴다. % 를 건드리지 않으므로 멱등이다.
    """
    return _HANGUL_OR_SPACE.sub(
        lambda m: "".join(f"%{b:02X}" for b in m.group().encode("utf-8")), url
    )


KST = timezone(timedelta(hours=9))


def _published_kst(entry):
    # feedparser 는 pubDate 를 UTC struct_time 으로 정규화한다. 8필드 계약의
    # published 는 타임존 표기 없는 KST 문자열이라 여기서 +9h 변환한다.
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None  # 피드에 날짜가 없으면 본문 추출 단계에서 채운다
    utc = datetime(*parsed[:6], tzinfo=timezone.utc)
    return utc.astimezone(KST).strftime("%Y-%m-%d %H:%M:%S")


def collect_new(db_path, feeds=FEEDS):
    """전 피드에서 신규 기사 목록을 돌려준다. 같은 link 는 두 번 반환되지 않는다."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS seen (link TEXT PRIMARY KEY, first_seen TEXT)"
    )
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
    items = []
    for feed in feeds:
        for rss_url in feed["rss"]:
            try:
                parsed = feedparser.parse(rss_url, agent=USER_AGENT)
            except Exception:
                # 피드 하나의 실패가 전체 수집을 막지 않게 격리. 다음 배치가 자연 재시도
                logger.warning("피드 파싱 실패, 스킵: %s %s", feed["company"], rss_url[:80])
                continue
            for entry in parsed.entries:
                link = encode_link((entry.get("link") or "").strip())
                title = (entry.get("title") or "").strip()
                if not link or not title:
                    continue
                inserted = conn.execute(
                    "INSERT OR IGNORE INTO seen VALUES (?, ?)", (link, now)
                ).rowcount
                if not inserted:
                    continue  # 이미 본 기사
                tags = [t.get("term") for t in entry.get("tags", []) if t.get("term")]
                items.append({
                    "company": feed["company"],
                    # Kafka key(article_id) 계산용. 8필드 메시지 본문에는 넣지 않는다
                    "publisher_id": feed["publisher_id"],
                    "title": title,
                    "link": link,
                    "published": _published_kst(entry),
                    # RSS category 태그 원문. 코드 매핑은 적재 변환(-66) 몫
                    "category_str": tags[0] if tags else None,
                })
    conn.commit()
    conn.close()
    return items


if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else "seen.sqlite"
    found = collect_new(db)
    per = {}
    for item in found:
        per[item["company"]] = per.get(item["company"], 0) + 1
    for company in sorted(per):
        print(f"{company}: {per[company]}건")
    print(f"신규 {len(found)}건")
