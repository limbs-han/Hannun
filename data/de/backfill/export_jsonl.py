"""백필 결과를 article_v1 JSONL 로 내보내기 (S15P21E105-108).

작업 DB 의 처리 완료(full/fallback) 행을 article_v1 레코드로 조립해 월별 JSONL
파일로 쓴다. 전 레코드가 스키마 검증을 통과해야 하며, 실패 레코드는 파일에 쓰지
않고 사유를 집계한다.

  python -m backfill.export_jsonl --db backfill_jobs.sqlite --out out/
"""

import argparse
import datetime as dt
import json
import logging
import os
import sqlite3

from jsonschema import Draft7Validator

from crawler.article_id import article_id

logger = logging.getLogger(__name__)

_SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "..", "schemas", "article_v1.json")
KST = dt.timezone(dt.timedelta(hours=9))


def _to_utc_z(kst_str):
    """KST 'YYYY-MM-DD HH:MM:SS' → UTC 'YYYY-MM-DDTHH:MM:SSZ'."""
    parsed = dt.datetime.strptime(kst_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=KST)
    return parsed.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_record(row):
    link, company, publisher_id, title, day, category_str, reporter, status, article, published, fetched_at = row
    # 페이지 추출 시각(KST) 우선, 없으면 엑셀 일자의 자정
    kst = published or f"{day[:4]}-{day[4:6]}-{day[6:8]} 00:00:00"
    category = (category_str or "").split(">")[0].strip() or "OTHER"
    return {
        "company": company,
        "title": title,
        "link": link,
        "published": _to_utc_z(kst),
        "category": category,
        "category_str": category_str or None,
        "reporter": reporter or None,
        "article": article,
        "schema_version": "1.0",
        "article_id": article_id(publisher_id, link),
        "publisher_id": publisher_id,
        "source_type": "DATASET",
        "language": "ko",
        "thumbnail_url": None,
        "crawled_at": fetched_at,
    }


def export(db_path, out_dir):
    with open(os.path.normpath(_SCHEMA_PATH), encoding="utf-8") as f:
        validator = Draft7Validator(json.load(f))
    os.makedirs(out_dir, exist_ok=True)
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT link, company, publisher_id, title, day, category_str, reporter,"
        " status, article, published, fetched_at FROM jobs"
        " WHERE status IN ('full', 'fallback') AND article IS NOT NULL AND article != ''"
    )
    stats = {"written": 0, "invalid": 0}
    handles = {}
    try:
        for row in rows:
            record = build_record(row)
            errors = list(validator.iter_errors(record))
            if errors:
                stats["invalid"] += 1
                logger.warning("스키마 위반, 제외: %s (%s)", record["link"][:60], errors[0].message)
                continue
            month = record["published"][:7].replace("-", "")
            if month not in handles:
                handles[month] = open(os.path.join(out_dir, f"articles_{month}.jsonl"),
                                      "a", encoding="utf-8")
            handles[month].write(json.dumps(record, ensure_ascii=False) + "\n")
            stats["written"] += 1
    finally:
        for h in handles.values():
            h.close()
        conn.close()
    return stats


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    print("완료:", export(args.db, args.out))
