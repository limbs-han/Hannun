import sqlite3

from openpyxl import Workbook

import backfill.bigkinds as bk
import backfill.fill_runner as fr
import backfill.export_jsonl as ex

HEADER = ["뉴스 식별자", "일자", "언론사", "기고자", "제목", "통합 분류1", "통합 분류2",
          "통합 분류3", "사건/사고 분류1", "사건/사고 분류2", "사건/사고 분류3", "인물",
          "위치", "기관", "키워드", "특성추출", "본문", "URL", "분석제외 여부"]


def _xlsx(path, rows):
    wb = Workbook()
    ws = wb.active
    ws.append(HEADER)
    for r in rows:
        ws.append(r)
    wb.save(path)


def _row(company="동아일보", title="제목", url="https://a.com/1", day="20240701",
         cat="정치>행정", reporter="김기자", body="이백자 본문", excluded=""):
    return ["id1", day, company, reporter, title, cat, "", "", "", "", "", "", "", "",
            "", "", body, url, excluded]


def test_load_jobs_filters_and_dedups(tmp_path):
    _xlsx(tmp_path / "NewsResult_20240701-20240707.xlsx", [
        _row(url="https://a.com/1"),
        _row(url="https://a.com/1", title="같은 링크 재수록"),
        _row(url="https://a.com/2", excluded="중복"),
        _row(url=""),
        _row(company="듣보신문", url="https://a.com/3"),
    ])
    _xlsx(tmp_path / "NewsResult_20250115-20250115_분석기사.xlsx", [_row(url="https://a.com/9")])  # 이름 패턴 밖 → 무시
    db = str(tmp_path / "jobs.sqlite")
    stats = bk.load_jobs(str(tmp_path), db)
    assert stats == {"loaded": 1, "excluded": 1, "no_url": 1, "dup": 1, "unknown_pub": 1}

    again = bk.load_jobs(str(tmp_path), db)  # 재실행해도 중복 적재 없음
    assert again["loaded"] == 0 and again["dup"] == 2  # 원본·재수록 행 모두 기존재


def test_fill_runner_full_fallback_and_resume(tmp_path, monkeypatch):
    _xlsx(tmp_path / "NewsResult_20240701-20240707.xlsx", [
        _row(url="https://a.com/ok", title="성공 기사"),
        _row(url="https://a.com/dead", title="죽은 기사", body="살아남을 200자"),
        _row(company="조선일보", url="https://b.com/js", title="스킵 대상", body="조선 200자"),
    ])
    db = str(tmp_path / "jobs.sqlite")
    bk.load_jobs(str(tmp_path), db)

    monkeypatch.setattr(fr.time, "sleep", lambda s: None)
    monkeypatch.setattr(fr, "fetch", lambda url: "html" if url.endswith("/ok") else None)
    monkeypatch.setattr(fr, "parse", lambda html, url=None: (
        {"article": "전문 본문 " * 30, "reporter": None, "published": "2024-07-01 10:00:00",
         "thumbnail_url": None} if html else None))

    class AllowAll:
        def __init__(self, ua):
            pass

        def allowed(self, url):
            return True

    monkeypatch.setattr(fr, "RobotsGate", AllowAll)

    counts = fr.run(db, limit_per_publisher=None)
    assert counts == {"full": 1, "fallback": 2}

    conn = sqlite3.connect(db)
    assert conn.execute("SELECT article FROM jobs WHERE link LIKE '%dead'").fetchone()[0] == "살아남을 200자"
    assert conn.execute("SELECT status FROM jobs WHERE link LIKE '%js'").fetchone()[0] == "fallback"
    conn.close()

    assert fr.run(db) == {"full": 0, "fallback": 0}  # 완주 후 재실행 = 0건


def test_export_builds_valid_article_v1(tmp_path, monkeypatch):
    _xlsx(tmp_path / "NewsResult_20240701-20240707.xlsx", [
        _row(url="https://a.com/ok", title="성공 기사"),
    ])
    db = str(tmp_path / "jobs.sqlite")
    bk.load_jobs(str(tmp_path), db)
    monkeypatch.setattr(fr.time, "sleep", lambda s: None)
    monkeypatch.setattr(fr, "fetch", lambda url: "html")
    monkeypatch.setattr(fr, "parse", lambda html, url=None: {
        "article": "전문 본문 " * 30, "reporter": "김기자", "published": "2024-07-01 10:00:00",
        "thumbnail_url": None})

    class AllowAll:
        def __init__(self, ua):
            pass

        def allowed(self, url):
            return True

    monkeypatch.setattr(fr, "RobotsGate", AllowAll)
    fr.run(db)

    stats = ex.export(db, str(tmp_path / "out"))
    assert stats == {"written": 1, "invalid": 0}
    import json
    line = (tmp_path / "out" / "articles_202407.jsonl").read_text(encoding="utf-8").strip()
    record = json.loads(line)
    assert record["published"] == "2024-07-01T01:00:00Z"  # KST 10:00 → UTC 01:00
    assert record["source_type"] == "DATASET"
    assert record["category"] == "정치"


def test_export_distrusts_drifted_page_date():
    # 페이지가 오늘 날짜를 노출한 경우: 엑셀 일자(20240707)를 믿는다
    row = ("https://a.com/1", "아시아투데이", "asiatoday", "제목", "20240707",
           "정치>선거", None, "full", "본문 " * 50, "2026-08-31 15:00:00", "2026-09-01T00:00:00Z")
    record = ex.build_record(row)
    assert record["published"] == "2024-07-06T15:00:00Z"  # KST 07-07 00:00 → UTC

    # 하루 이내 차이(자정 넘김 등)는 페이지 시각을 그대로 쓴다
    row = row[:9] + ("2024-07-08 01:00:00",) + row[10:]
    record = ex.build_record(row)
    assert record["published"] == "2024-07-07T16:00:00Z"
