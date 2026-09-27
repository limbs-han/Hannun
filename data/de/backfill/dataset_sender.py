"""SSAFY 과거 데이터셋을 운영 Kafka(news.article.raw)로 보내는 송신기 (S15P21E105-114).

CSV 를 스트리밍으로 읽어 확정 스펙으로 변환·정제하고, 스로틀을 지켜 발행한다.
sqlite 체크포인트에 파일별 진행 행 번호를 기록해 중단해도 이어서 실행된다.
본문(article)은 BE 미사용이라 싣지 않는다 — 본문은 HDFS(article_v1) 경로가 담당.

사용:
  python -m backfill.dataset_sender --dry-run                # 앞 5건 미리보기
  KAFKA_BROKER=... python -m backfill.dataset_sender --send  # 전량 (체크포인트 이어서)
  ... --send --limit 10000                                   # 파일럿
"""

import argparse
import csv
import html
import json
import logging
import os
import re
import sqlite3
import sys
import time

from crawler.article_id import article_id
from crawler.publishers import PUBLISHER_ID
from crawler.rss_collector import encode_link

logger = logging.getLogger(__name__)

DATASET_DIR = os.environ.get("DATASET_DIR", r"C:\Users\SSAFY\Downloads\news_dataset")
BROKER = os.environ.get("KAFKA_BROKER", "localhost:29092")
TOPIC = os.environ.get("ARTICLE_TOPIC", "news.article.raw")
RATE_PER_SEC = float(os.environ.get("SEND_RATE_PER_SEC", "200"))

FILES = ["2019", "2020", "2021", "2022", "2023", "2024_1st_half", "2025_1st_half"]
ERRORISH = re.compile(r"index out of range|Traceback|NoneType|Error|Exception")


def clean_text(s):
    """깨진 HTML 엔티티(amp;#39; 등)까지 복원해 해제한다."""
    s = re.sub(r"&?amp;(?=#|[a-z]+;)", "&", s)
    return html.unescape(html.unescape(s)).strip()


def build_message(row):
    """CSV 8필드 행을 news.article.raw 메시지로 변환한다. 부적합 행이면 None."""
    company, title, link, published, category, category_str, reporter, _article = row
    company = company.strip()
    link = encode_link(link.strip())
    title = clean_text(title)
    published = published.strip()
    if not (company and title and link.startswith("http") and published):
        return None
    if len(link) > 1000 or not link.isascii():
        return None  # 스펙 제한 초과 — 매칭 키라 자르면 안 되므로 제외
    if len(published) == 16:
        published += ":00"
    reporter = clean_text(reporter)
    category, category_str = category.strip(), category_str.strip()
    return {
        "company": company[:100],
        "title": title[:500],
        "link": link,
        "published": published.replace(" ", "T") + "+09:00",
        "category": None if (not category or ERRORISH.search(category)) else category[:100],
        "category_str": None if (not category_str or ERRORISH.search(category_str)) else category_str[:100],
        "reporter": None if (not reporter or reporter == company) else reporter[:100],
        "thumbnail_url": None,
    }


def _preflight(broker):
    """송신 시작 전에 브로커 접속을 확인한다. 미설정 시 조용히 localhost 로
    가서 15,000건이 헛도는 사고(2026-09-01 실측)를 막는다."""
    from confluent_kafka.admin import AdminClient
    try:
        AdminClient({"bootstrap.servers": broker}).list_topics(timeout=10)
    except Exception as error:
        raise SystemExit(
            f"Kafka 브로커({broker})에 연결할 수 없습니다. "
            "운영 송신이라면 KAFKA_BROKER 환경변수를 설정하세요."
        ) from error


class Checkpoint:
    """파일별 진행 행 번호와 송신한 링크를 기록한다."""

    def __init__(self, path):
        self._conn = sqlite3.connect(path)
        self._conn.execute("CREATE TABLE IF NOT EXISTS progress (file TEXT PRIMARY KEY, row INTEGER)")
        self._conn.execute("CREATE TABLE IF NOT EXISTS sent_links (link TEXT PRIMARY KEY)")

    def done_rows(self, name):
        got = self._conn.execute("SELECT row FROM progress WHERE file=?", (name,)).fetchone()
        return got[0] if got else 0

    def mark(self, name, row_no, link):
        self._conn.execute("INSERT OR REPLACE INTO progress VALUES (?, ?)", (name, row_no))
        if link:
            self._conn.execute("INSERT OR IGNORE INTO sent_links VALUES (?)", (link,))

    def total_sent(self):
        """지금까지 전달 확인까지 끝난 누적 송신 수."""
        return self._conn.execute("SELECT COUNT(*) FROM sent_links").fetchone()[0]

    def already_sent(self, link):
        return self._conn.execute("SELECT 1 FROM sent_links WHERE link=?", (link,)).fetchone() is not None

    def commit(self):
        self._conn.commit()

    def close(self):
        # 커밋 안 된 mark 는 롤백된다 — 전달 미확인 구간을 기록에 남기지 않기 위함
        self._conn.close()


def iter_rows(name):
    csv.field_size_limit(10_000_000)
    path = os.path.join(DATASET_DIR, f"ssafy_dataset_news_{name}.csv")
    with open(path, encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.reader(f, delimiter="|", quotechar='"')
        next(reader, None)
        for row_no, row in enumerate(reader, start=1):
            if len(row) == 8:
                yield row_no, row


def run(send, limit=None, checkpoint_path="dataset_sender_checkpoint.sqlite", producer=None,
        verbose=False):
    stats = {"sent": 0, "dedup": 0, "invalid": 0}
    ckpt = Checkpoint(checkpoint_path)
    base_sent = ckpt.total_sent()  # 표시 번호를 이전 실행에서 이어가기 위한 누적
    if base_sent:
        logger.info("이전까지 %s건 송신 완료 상태에서 이어서 시작", f"{base_sent:,}")
    if send and producer is None:
        _preflight(BROKER)
        from confluent_kafka import Producer
        producer = Producer({"bootstrap.servers": BROKER, "acks": "all"})

    delivery_errors = []

    def _on_delivery(error, _msg):
        if error is not None:
            delivery_errors.append(str(error))

    def _sync():
        """전달 확인 후에만 체크포인트를 커밋한다. 실패 시 기록하지 않아
        재실행에서 그 구간을 다시 보낸다 (at-least-once)."""
        if send:
            remaining = producer.flush(60)
            if remaining or delivery_errors:
                raise RuntimeError(
                    f"전송 미확인 {remaining}건, 실패 {len(delivery_errors)}건 "
                    f"(첫 오류: {delivery_errors[0] if delivery_errors else '없음'}) — "
                    "체크포인트를 기록하지 않았습니다. 원인 해결 후 재실행하면 이어서 보냅니다."
                )
        ckpt.commit()

    interval = 1.0 / RATE_PER_SEC
    next_slot = time.monotonic()
    try:
        for name in FILES:
            start_row = ckpt.done_rows(name)
            for row_no, row in iter_rows(name):
                if row_no <= start_row:
                    continue
                if limit is not None and stats["sent"] >= limit:
                    _sync()
                    return stats
                message = build_message(row)
                if message is None:
                    stats["invalid"] += 1
                    ckpt.mark(name, row_no, None)
                    continue
                if ckpt.already_sent(message["link"]):
                    stats["dedup"] += 1
                    ckpt.mark(name, row_no, None)
                    continue
                if send:
                    now = time.monotonic()
                    if now < next_slot:
                        time.sleep(next_slot - now)
                    next_slot = max(next_slot + interval, now)
                    publisher = PUBLISHER_ID.get(message["company"], message["company"])
                    producer.produce(TOPIC, key=article_id(publisher, message["link"]),
                                     value=json.dumps(message, ensure_ascii=False),
                                     on_delivery=_on_delivery)
                    producer.poll(0)
                stats["sent"] += 1
                ckpt.mark(name, row_no, message["link"])
                if verbose:
                    print(f"[{base_sent + stats['sent']:,}] {message['company']} | {message['title'][:50]}", flush=True)
                elif stats["sent"] % 1000 == 0:
                    logger.info("%s 누적 %s건 송신, 마지막: %s | %s",
                                name, f"{base_sent + stats['sent']:,}", message["company"], message["title"][:40])
                if stats["sent"] % 5000 == 0:
                    _sync()
                    logger.info("%s: %s행, 누적 %s", name, f"{row_no:,}", stats)
            _sync()
            logger.info("%s 완료: %s", name, stats)
            _sync()
            return stats
    finally:
        ckpt.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    ap = argparse.ArgumentParser()
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="앞 5건 변환 결과만 출력")
    group.add_argument("--send", action="store_true", help="실제 송신")
    ap.add_argument("--limit", type=int, help="송신 건수 상한 (파일럿용)")
    ap.add_argument("--files", nargs="+", choices=FILES, help="보낼 파일만 지정 (예: --files 2019)")
    ap.add_argument("--verbose", action="store_true", help="보내는 기사를 건별로 출력")
    args = ap.parse_args()
    if args.files:
        FILES[:] = args.files

    if args.dry_run:
        shown = 0
        for name in FILES:
            for _no, row in iter_rows(name):
                message = build_message(row)
                if message:
                    print(json.dumps(message, ensure_ascii=False, indent=2))
                    shown += 1
                if shown >= 5:
                    sys.exit(0)
    else:
        result = run(send=True, limit=args.limit, verbose=args.verbose)
        print(f"완료: {result}")
