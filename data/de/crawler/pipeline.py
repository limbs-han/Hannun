"""수집→본문 추출→Kafka 발행 파이프라인 (S15P21E105-62).

15분 배치 1회분: 신규 기사 목록을 만들고, 본문을 추출해 8필드 기사 JSON 으로
조립한 뒤 Kafka 토픽에 발행한다. published 를 끝내 못 구한 기사는 비기사
페이지일 가능성이 높아 발행하지 않는다.
"""

import json
import os
import sys

from confluent_kafka import Producer

from crawler.extractor import fetch, parse
from crawler.rss_collector import collect_new

BROKER = os.environ.get("KAFKA_BROKER", "localhost:29092")
TOPIC = os.environ.get("ARTICLE_TOPIC", "news.article.realtime.v1")


def build_article(item, parsed):
    """수집 항목과 추출 결과를 8필드 기사 JSON 으로 합친다."""
    return {
        "company": item["company"],
        "title": item["title"],
        "link": item["link"],
        "published": item.get("published") or parsed.get("published"),
        "category": None,  # 코드 매핑은 적재 변환(-66) 몫
        "category_str": item.get("category_str"),
        "reporter": parsed.get("reporter"),
        "article": parsed["article"],
    }


def run(db_path, producer=None, fetch_fn=fetch, feeds=None):
    """배치 1회 실행. (발행 건수, 스킵 건수) 를 돌려준다."""
    kwargs = {"feeds": feeds} if feeds is not None else {}
    items = collect_new(db_path, **kwargs)
    if producer is None:
        producer = Producer({"bootstrap.servers": BROKER})
    sent = skipped = 0
    for item in items:
        parsed = parse(fetch_fn(item["link"]), url=item["link"])
        if not parsed:
            skipped += 1  # 본문 없음·100자 미만. 실패 로그 정책은 -63
            continue
        message = build_article(item, parsed)
        if not message["published"]:
            skipped += 1  # 발행시각 없음 = 비기사 페이지로 간주
            continue
        producer.produce(
            TOPIC,
            key=message["link"],
            value=json.dumps(message, ensure_ascii=False),
        )
        sent += 1
    producer.flush()
    return sent, skipped


if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else "seen.sqlite"
    sent, skipped = run(db)
    print(f"발행 {sent}건, 스킵 {skipped}건")
