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
