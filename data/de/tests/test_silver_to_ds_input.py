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


def test_day_dir_groups_by_year_without_partition_prefix():
    # 연도로 묶는 이유는 전체를 내리면 날짜 폴더가 2,800개가 되기 때문이다.
    # dt= 접두어는 Spark 용이라 DS 에게는 아무 역할을 하지 않는다
    assert ex.day_dir("/ds_input", "2026-09-07").replace("\\", "/") == "/ds_input/2026/2026-09-07"
    assert ex.day_dir("/ds_input", "2019-01-01").replace("\\", "/") == "/ds_input/2019/2019-01-01"


def test_staging_path_is_unique_per_process():
    import os
    final = "/ds_input/2026-09-07/articles.jsonl"
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


def test_normalize_staging_renames_single_part_and_moves_into_year(tmp_path):
    line = chr(123) + chr(34) + "a" + chr(34) + ":1" + chr(125) + chr(10)  # {"a":1} 한 줄
    staging = _staging(tmp_path, "2019-03-04",
                       {"part-00000-a.c000.json": line, "_SUCCESS": ""})
    assert ex.normalize_staging(str(staging), str(tmp_path / "out")) == 1
    moved = tmp_path / "out" / "2019" / "2019-03-04" / "articles.jsonl"
    # 확장자가 .jsonl 이어야 DS 가 줄 단위로 읽는다
    assert moved.read_text(encoding="utf-8") == line
    assert not staging.exists()  # 임시 폴더는 남기지 않는다


def test_normalize_staging_keeps_every_part_when_day_is_split(tmp_path):
    staging = _staging(tmp_path, "2020-05-06",
                       {"part-00000-a.c000.json": "a", "part-00001-b.c000.json": "b"})
    ex.normalize_staging(str(staging), str(tmp_path / "out"))
    day = tmp_path / "out" / "2020" / "2020-05-06"
    assert sorted(f.name for f in day.iterdir()) == ["articles-0.jsonl", "articles-1.jsonl"]
    # DS 는 폴더 안 파일을 모두 읽으므로 하루가 여러 파일이어도 된다
    assert sorted(f.read_text(encoding="utf-8") for f in day.iterdir()) == ["a", "b"]
