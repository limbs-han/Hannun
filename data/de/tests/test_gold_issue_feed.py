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


# --- 품질 지표 (S15P21E105-130) -------------------------------------------

def _counts(**over):
    base = {"rows": 100, "other_labels": 68, "matched": 100, "neutral": 82,
            "briefing_fallbacks": 41, "issue_size_max": 89}
    base.update(over)
    return base


def _values(lines):
    return {name.split("{")[0]: float(value)
            for name, value in (line.split(" ", 1) for line in lines)}


def test_quality_lines_report_ratios_not_raw_counts():
    # 건수는 날마다 달라 비교가 안 된다. 비율이라야 어제와 오늘을 겹쳐 볼 수 있다
    values = _values(g.quality_lines(_counts()))
    assert values["pipeline_gold_viewpoint_other_ratio"] == 0.68
    assert values["pipeline_gold_stance_neutral_ratio"] == 0.82
    assert values["pipeline_gold_briefing_fallback_ratio"] == 0.41


def test_neutral_ratio_counts_only_rows_ds2_actually_labelled():
    # 관점이 안 붙은 기사는 중립이 아니라 결측이다. 분모에 넣으면 중립 비율이 낮게 보인다
    values = _values(g.quality_lines(_counts(rows=100, matched=50, neutral=40)))
    assert values["pipeline_gold_stance_neutral_ratio"] == 0.8


def test_biggest_issue_size_goes_out_as_is():
    # 과하게 뭉치는지 보는 값이라 비율로 바꾸면 뜻이 사라진다
    assert _values(g.quality_lines(_counts()))["pipeline_gold_issue_size_max"] == 89


def test_empty_day_sends_no_ratios():
    # 분모가 0 일 때 0 을 보내면 "전부 정상"으로 읽힌다. 빈 날은 값을 안 보내야
    # 그래프가 끊겨 보이고, 끊긴 것이 눈에 띈다
    values = _values(g.quality_lines(_counts(rows=0, matched=0)))
    assert "pipeline_gold_viewpoint_other_ratio" not in values
    assert "pipeline_gold_stance_neutral_ratio" not in values
    assert "pipeline_gold_issue_size_max" in values


def test_observed_broken_labels_start_with_the_prefix_we_look_for():
    # 실측(9/19~21) 상위 두 라벨. 이 둘이 전체의 68.5% 였다
    for label in ("기타 관점", "기타 중립 관점"):
        assert label.startswith(g.OTHER_LABEL_PREFIX)
    assert not "경쟁력 강화".startswith(g.OTHER_LABEL_PREFIX)
