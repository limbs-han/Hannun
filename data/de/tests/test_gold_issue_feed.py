import os
import time

from jobs import gold_issue_feed as g


def _touch(path, mtime):
    path.write_text("{}", encoding="utf-8")
    os.utime(path, (mtime, mtime))


def test_ds2_file_for_picks_newest_after_window(tmp_path):
    """창 폴더가 쓰인 뒤 만들어진 가장 최근 파일을 고른다 (S15P21E105-69)."""
    gold = tmp_path / "gold"
    out = tmp_path / "out"
    win = gold / "issue_summary" / "window_start=2026-09-15"
    win.mkdir(parents=True)
    out.mkdir()
    now = time.time()
    os.utime(win, (now - 100, now - 100))
    _touch(out / "2026-09-14.jsonl", now - 500)   # 창보다 앞선 옛 파일
    _touch(out / "2026-09-15.jsonl", now - 50)    # 창 뒤
    _touch(out / "2026-09-16.jsonl", now - 10)    # 창 뒤, 가장 최근
    picked = g.ds2_file_for("2026-09-15", ds_gold=str(gold), ds_output=str(out))
    assert os.path.basename(picked) == "2026-09-16.jsonl"


def test_ds2_file_for_skips_files_older_than_window(tmp_path):
    """사슬이 창을 다시 쓰면 옛 DS2 파일은 걸러진다. 다른 창의 이슈 번호는 붙으면 안 된다."""
    gold = tmp_path / "gold"
    out = tmp_path / "out"
    win = gold / "issue_summary" / "window_start=2026-09-15"
    win.mkdir(parents=True)
    out.mkdir()
    now = time.time()
    os.utime(win, (now, now))
    _touch(out / "2026-09-16.jsonl", now - 300)
    assert g.ds2_file_for("2026-09-15", ds_gold=str(gold), ds_output=str(out)) is None


def test_ds2_file_for_without_window_folder_takes_any(tmp_path):
    """창 폴더가 아직 없으면 기준 시각이 0 이라 있는 파일 중 최근 것을 쓴다."""
    out = tmp_path / "out"
    out.mkdir()
    _touch(out / "a.jsonl", time.time() - 10)
    picked = g.ds2_file_for("2026-01-01", ds_gold=str(tmp_path / "none"), ds_output=str(out))
    assert os.path.basename(picked) == "a.jsonl"


def test_ds2_file_for_empty_dir(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    assert g.ds2_file_for("2026-01-01", ds_gold=str(tmp_path), ds_output=str(out)) is None


def _strip(text):
    """브리핑 임시값에서 머리말을 걷어내는 정규식을 파이썬으로 그대로 적용한다.

    실제 잡은 Spark 표현식이라 세션 없이는 못 돌린다. 위험한 부분은 정규식이므로
    같은 패턴을 여기서 검증한다.
    """
    import re
    for pattern in (g._DATELINE, g._BYLINE, g._LEAD_EQUALS):
        text = re.sub(pattern, "", text)
    return text


def test_fallback_briefing_strips_dateline_and_byline():
    raw = "(평창=연합뉴스) 임보연 기자 = 국내 대표 민속예술 축제가 열린다."
    assert _strip(raw) == "국내 대표 민속예술 축제가 열린다."


def test_fallback_briefing_strips_dateline_without_byline():
    assert _strip("[서울=뉴시스] 정부가 대책을 내놨다.") == "정부가 대책을 내놨다."


def test_fallback_briefing_keeps_reporter_in_sentence():
    # "=" 가 없으면 기자명이 아니라 문장의 일부다. 지우면 "가 말했다" 만 남는다
    raw = "김철수 기자가 현장을 찾았다."
    assert _strip(raw) == raw


def test_fallback_briefing_cuts_at_sentence_end():
    import re
    head = "첫 문장이다. 둘째 문장이다. 셋째 문장은 잘린 채 제67"
    assert re.match(r"^(.*[.!?])", head).group(1) == "첫 문장이다. 둘째 문장이다."
