"""수집→본문 추출→Kafka 발행 파이프라인 (S15P21E105-62, -63).

15분 배치 1회분: 신규 기사 목록을 만들고, 본문을 추출해 8필드 기사 JSON 으로
조립한 뒤 Kafka 토픽에 발행한다. Kafka key 는 article_id(계약 S15P21E105-55)다.
published 를 끝내 못 구한 기사는 비기사 페이지일 가능성이 높아 발행하지 않는다.

수집 예절(-63): 도메인별 1초 간격을 지키고 robots.txt 가 금지한 URL 은 접속하지
않는다. 기사 하나의 실패는 그 기사만 스킵하고 로그를 남긴다.
"""

import json
import logging
import os
import sys

from confluent_kafka import Producer

from crawler.article_id import article_id
from crawler.extractor import fetch, parse
from crawler.politeness import RateLimiter, RobotsGate
from crawler.rss_collector import USER_AGENT, collect_new

logger = logging.getLogger(__name__)

BROKER = os.environ.get("KAFKA_BROKER", "localhost:29092")
TOPIC = os.environ.get("ARTICLE_TOPIC", "news.article.raw")


def _on_delivery(err, msg):
    if err is not None:
        logger.warning("Kafka 발행 실패: %s (key=%s)", err, msg.key())


def _to_iso_kst(published):
    """타임존 없는 KST 문자열을 +09:00 오프셋 ISO-8601 로 바꾼다 (송신 스펙)."""
    if not published:
        return None
    return published.strip().replace(" ", "T") + "+09:00"


def build_article(item, parsed):
    """수집 항목과 추출 결과를 news.article.raw 메시지로 합친다."""
    return {
        "company": item["company"],
        "title": item["title"],
        "link": item["link"],
        "published": _to_iso_kst(item.get("published") or parsed.get("published")),
        # 받아온 피드에서 온 값 (S15P21E105-61). 섹션 피드가 없는 분야는 빈다
        "category": item.get("category"),
        "category_str": item.get("category_str"),
        "reporter": parsed.get("reporter"),
        "thumbnail_url": parsed.get("thumbnail_url"),
        "article": parsed["article"],
    }


def run(db_path, producer=None, fetch_fn=fetch, feeds=None, limiter=None, robots=None):
    """배치 1회 실행. (발행 건수, 스킵 건수) 를 돌려준다."""
    kwargs = {"feeds": feeds} if feeds is not None else {}
    items = collect_new(db_path, **kwargs)
    if producer is None:
        producer = Producer({"bootstrap.servers": BROKER, "acks": "all"})
    limiter = limiter or RateLimiter()
    robots = robots or RobotsGate(USER_AGENT)
    sent = skipped = 0
    for item in items:
        link = item["link"]
        try:
            if not robots.allowed(link):
                logger.warning("robots.txt 차단, 스킵: %s", link)
                skipped += 1
                continue
            limiter.wait(link)
            parsed = parse(fetch_fn(link), url=link)
        except Exception:
            logger.warning("기사 처리 실패, 스킵: %s", link, exc_info=True)
            skipped += 1
            continue
        if not parsed:
            logger.warning("본문 없음 또는 100자 미만, 스킵: %s", link)
            skipped += 1
            continue
        message = build_article(item, parsed)
        if not message["published"]:
            logger.warning("발행시각 없음(비기사 페이지 가능성), 스킵: %s", link)
            skipped += 1
            continue
        producer.produce(
            TOPIC,
            # key = article_id: utm 등 추적 파라미터가 달라도 같은 기사는 같은
            # 파티션으로 가고, 적재 변환의 article_id 필드와 같은 값이 된다
            key=article_id(item["publisher_id"], link),
            value=json.dumps(message, ensure_ascii=False),
            on_delivery=_on_delivery,
        )
        producer.poll(0)
        sent += 1
    producer.flush()
    return sent, skipped


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    db = sys.argv[1] if len(sys.argv) > 1 else "seen.sqlite"
    sent, skipped = run(db)
    print(f"발행 {sent}건, 스킵 {skipped}건")
