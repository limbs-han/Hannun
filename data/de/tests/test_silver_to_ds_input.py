import datetime as dt
import json

from jobs import silver_to_ds_input as ex


class FakeRow:
    def __init__(self, data):
        self._data = data

    def asDict(self):
        return dict(self._data)


def test_yesterday_uses_korean_date_not_utc():
    # UTC 로는 9월 7일 15시지만 한국은 이미 9월 8일 → 어제는 9월 7일이다
    now = dt.datetime(2026, 9, 7, 15, 30, tzinfo=dt.timezone.utc)
    assert ex.yesterday_kst(now) == "2026-09-07"
    # UTC 9월 8일 01시는 한국 9월 8일 10시 → 어제는 그대로 9월 7일
    assert ex.yesterday_kst(dt.datetime(2026, 9, 8, 1, 0, tzinfo=dt.timezone.utc)) == "2026-09-07"


def test_target_days_defaults_to_recent_window_ending_yesterday():
    now = dt.datetime(2026, 9, 8, 1, 0, tzinfo=dt.timezone.utc)  # 한국 9월 8일
    assert ex.target_days([], recent=3, now=now) == ["2026-09-05", "2026-09-06", "2026-09-07"]
    assert ex.target_days([], recent=1, now=now) == ["2026-09-07"]
    assert ex.target_days(["2026-09-01", "2026-09-03"], recent=1) == [
        "2026-09-01", "2026-09-02", "2026-09-03"]
    assert ex.target_days(["2026-09-01"], recent=3) == ["2026-09-01"]


def test_json_line_drops_partition_column_and_keeps_hangul():
    row = FakeRow({"company": "연합뉴스", "title": "제목", "article": "본문", "dt": "2026-09-06"})
    parsed = json.loads(ex.to_json_line(row))
    assert "dt" not in parsed  # article_v1 에 없는 필드라 DS 에 넘기지 않는다
    assert parsed["company"] == "연합뉴스"
    assert "연합뉴스" in ex.to_json_line(row)  # 한글이 그대로 보여야 사람이 읽을 수 있다


def test_day_file_is_one_file_per_day_under_year_folder():
    # 하루에 폴더를 두지 않는다 — 파일이 하나뿐이라 폴더가 아무 역할을 하지 않는다.
    # dt= 접두어는 Spark 용이라 DS 에게는 쓸모없다
    got = ex.day_file("/ds_input", "2026-09-07").replace(chr(92), "/")
    assert got == "/ds_input/2026/2026-09-07.jsonl"
    old = ex.day_file("/ds_input", "2019-01-01").replace(chr(92), "/")
    assert old == "/ds_input/2019/2019-01-01.jsonl"


def test_staging_path_is_unique_per_process():
    import os
    final = "/ds_input/2026/2026-09-07.jsonl"
    staging = ex.staging_path(final)
    assert staging.startswith(final + ".tmp.")
    assert str(os.getpid()) in staging  # 두 프로세스가 같은 날짜를 내려도 섞이지 않는다
    assert staging != final


def _staging(tmp_path, day, parts):
    d = tmp_path / "_staging" / f"dt={day}"
    d.mkdir(parents=True)
    for name, text in parts.items():
        (d / name).write_text(text, encoding="utf-8")
    return tmp_path / "_staging"


def test_normalize_staging_moves_single_part_to_day_file(tmp_path):
    line = chr(123) + chr(34) + "a" + chr(34) + ":1" + chr(125) + chr(10)  # {"a":1} 한 줄
    staging = _staging(tmp_path, "2019-03-04",
                       {"part-00000-a.c000.json": line, "_SUCCESS": ""})
    assert ex.normalize_staging(str(staging), str(tmp_path / "out")) == 1
    moved = tmp_path / "out" / "2019" / "2019-03-04.jsonl"
    # 확장자가 .jsonl 이어야 DS 가 줄 단위로 읽는다
    assert moved.read_text(encoding="utf-8") == line
    assert not staging.exists()  # 임시 폴더는 남기지 않는다


def test_normalize_staging_joins_split_day_into_one_file(tmp_path):
    # 하루가 쪼개져도 파일 하나로 합친다 — 조각 하나만 읽어 나머지를 놓치는 일을 막는다
    a = chr(123) + chr(34) + "a" + chr(34) + ":1" + chr(125) + chr(10)
    b = chr(123) + chr(34) + "b" + chr(34) + ":2" + chr(125) + chr(10)
    staging = _staging(tmp_path, "2020-05-06",
                       {"part-00000-a.c000.json": a, "part-00001-b.c000.json": b})
    ex.normalize_staging(str(staging), str(tmp_path / "out"))
    year = tmp_path / "out" / "2020"
    assert [f.name for f in year.iterdir()] == ["2020-05-06.jsonl"]  # 하루 = 파일 하나
    assert year.joinpath("2020-05-06.jsonl").read_text(encoding="utf-8") == a + b


def test_stale_days_picks_missing_and_outdated_only(tmp_path):
    import os
    out = tmp_path / "out"
    (out / "2026").mkdir(parents=True)
    fresh = out / "2026" / "2026-09-07.jsonl"
    fresh.write_text("x", encoding="utf-8")
    os.utime(fresh, (2000, 2000))  # 파일이 silver 보다 최신
    old = out / "2026" / "2026-06-09.jsonl"
    old.write_text("x", encoding="utf-8")
    os.utime(old, (1000, 1000))   # 파일이 silver 보다 뒤처짐
    mtimes = {"2026-09-07": 1500.0, "2026-06-09": 1800.0, "2026-09-08": 1900.0}
    # 뒤처진 옛 날짜와 파일이 없는 날짜만 고른다. 최근 며칠이라는 창을 쓰지 않는 이유는
    # RSS 가 몇 달 전 기사를 뒤늦게 주면 그 날짜가 창 밖으로 밀려나기 때문이다
    assert ex.stale_days(mtimes, str(out)) == ["2026-06-09", "2026-09-08"]


def test_stale_days_empty_when_everything_current(tmp_path):
    import os
    out = tmp_path / "out"
    (out / "2026").mkdir(parents=True)
    f = out / "2026" / "2026-09-07.jsonl"
    f.write_text("x", encoding="utf-8")
    os.utime(f, (3000, 3000))
    assert ex.stale_days({"2026-09-07": 1000.0}, str(out)) == []


def test_stale_by_signature_picks_changed_and_unknown_days():
    signatures = {"2026-09-06": "aaa", "2026-09-07": "bbb", "2026-09-08": "ccc"}
    state = {"2026-09-06": "aaa", "2026-09-07": "old"}
    # 지문이 같은 날짜는 건너뛰고, 달라진 날짜와 기록에 없는 날짜만 고른다
    assert ex.stale_by_signature(signatures, state) == ["2026-09-07", "2026-09-08"]


def test_stale_by_signature_takes_everything_without_state():
    # 기록이 없으면 전체를 다시 내린다. 파케이에서 내려준 파일을 믿지 않는다
    signatures = {"2019-01-01": "a", "2026-09-08": "b"}
    assert ex.stale_by_signature(signatures, {}) == ["2019-01-01", "2026-09-08"]


def test_state_round_trip_and_missing_file(tmp_path):
    path = str(tmp_path / "state" / "ds_input_export.json")
    assert ex.load_state(path) == {}  # 첫 실행
    ex.save_state(path, {"2026-09-08": "abc"})
    assert ex.load_state(path) == {"2026-09-08": "abc"}


def test_load_state_survives_broken_file(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{ 깨진", encoding="utf-8")
    # 깨진 기록은 빈 값으로 본다. 전체를 다시 내리지만 데이터가 빠지지는 않는다
    assert ex.load_state(str(path)) == {}
