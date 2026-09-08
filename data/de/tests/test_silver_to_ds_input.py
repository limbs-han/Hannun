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


def test_day_dir_has_no_partition_prefix():
    # DS 는 Spark 가 아니라 파일 경로로 읽어서 dt= 접두어가 아무 역할을 하지 않는다
    assert ex.day_dir("/ds_input", "2026-09-07").replace("\\", "/") == "/ds_input/2026-09-07"


def test_staging_path_is_unique_per_process():
    import os
    final = "/ds_input/2026-09-07/articles.jsonl"
    staging = ex.staging_path(final)
    assert staging.startswith(final + ".tmp.")
    assert str(os.getpid()) in staging  # 두 프로세스가 같은 날짜를 내려도 섞이지 않는다
    assert staging != final
