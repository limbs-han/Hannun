"""백필 본문 채움 러너 (S15P21E105-108).

작업 DB(jobs)의 todo 기사를 언론사별 스레드로 병렬 처리한다. 각 스레드는 자기
도메인에만 1초 간격으로 접근하고, robots 가 금지하거나 추출이 실패하면 빅카인즈
200자 본문으로 대체(fallback)한다. status 갱신이 곧 체크포인트라 언제 중단해도
재실행하면 이어서 돈다.

사용:
  python -m backfill.fill_runner --db backfill_jobs.sqlite            # 전체
  python -m backfill.fill_runner --db backfill_jobs.sqlite --limit 1000  # 파일럿
"""

import argparse
import datetime as dt
import logging
import queue
import sqlite3
import threading
import time

from crawler.extractor import fetch, parse
from crawler.politeness import RobotsGate
from crawler.rss_collector import USER_AGENT

logger = logging.getLogger(__name__)

# 본문이 정적 HTML 에 없거나(조선일보) robots 전면 금지(내일신문)라 fetch 가
# 항상 헛걸음인 곳. 시도하지 않고 바로 200자 대체해 언론사당 수십 시간을 아낀다
SKIP_FETCH = {"chosun", "naeil"}


def _now_utc():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _worker(db_path, publisher_id, limit, counts, lock):
    conn = sqlite3.connect(db_path, timeout=60)
    robots = RobotsGate(USER_AGENT)
    done = 0
    while limit is None or done < limit:
        row = conn.execute(
            "SELECT link, body200 FROM jobs WHERE publisher_id=? AND status='todo' LIMIT 1",
            (publisher_id,),
        ).fetchone()
        if row is None:
            break
        link, body200 = row
        article = published = None
        if publisher_id not in SKIP_FETCH and robots.allowed(link):
            time.sleep(1)  # 도메인당 1초 간격 (스레드=도메인이라 sleep 으로 충분)
            try:
                parsed = parse(fetch(link), url=link)
            except Exception:
                parsed = None
            if parsed:
                article, published = parsed["article"], parsed["published"]
        status = "full" if article else "fallback"
        conn.execute(
            "UPDATE jobs SET status=?, article=?, published=?, fetched_at=? WHERE link=?",
            (status, article if article else body200, published, _now_utc(), link),
        )
        conn.commit()
        done += 1
        with lock:
            counts[status] += 1
            total = counts["full"] + counts["fallback"]
            if total % 500 == 0:
                logger.info("진행 %s건: %s", f"{total:,}", dict(counts))
    conn.close()


def run(db_path, limit_per_publisher=None):
    conn = sqlite3.connect(db_path)
    publishers = [p for (p,) in conn.execute(
        "SELECT DISTINCT publisher_id FROM jobs WHERE status='todo'")]
    conn.close()
    counts = {"full": 0, "fallback": 0}
    lock = threading.Lock()
    threads = [
        threading.Thread(target=_worker, args=(db_path, p, limit_per_publisher, counts, lock),
                         name=p, daemon=True)
        for p in publishers
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return counts


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--limit", type=int, help="언론사당 처리 상한 (파일럿용)")
    args = ap.parse_args()
    print("완료:", run(args.db, args.limit))
