import backfill.dataset_sender as ds


def test_build_message_cleans_and_formats():
    row = ["동아일보", "제목 amp;#39;인용amp;#39; &amp;quot;끝&amp;quot;",
           "https://a.com/기사?x=1", "2025-01-01 01:40", "문화", "", "동아일보", "본문"]
    msg = ds.build_message(row)
    assert msg["title"] == "제목 '인용' \"끝\""
    assert msg["link"] == "https://a.com/%EA%B8%B0%EC%82%AC?x=1"
    assert msg["published"] == "2025-01-01T01:40:00+09:00"
    assert msg["reporter"] is None          # 기자명 자리에 언론사명 → null
    assert msg["category_str"] is None      # 빈 값 → null


def test_build_message_rejects_errorish_category_and_bad_rows():
    ok = ["서울신문", "제목", "https://a.com/1", "2025-04-21 23:59:37",
          "list index out of range", "정치>행정", "이은주 기자", "본문"]
    msg = ds.build_message(ok)
    assert msg["category"] is None
    assert msg["category_str"] == "정치>행정"
    assert msg["reporter"] == "이은주 기자"

    assert ds.build_message(["회사", "제목", "not-a-url", "2025-01-01 00:00", "", "", "", ""]) is None
    assert ds.build_message(["회사", "제목", "https://a.com/" + "x" * 1000, "2025-01-01 00:00", "", "", "", ""]) is None


class FakeProducer:
    def __init__(self):
        self.messages = []

    def produce(self, topic, key, value, on_delivery=None):
        self.messages.append((key, value))
        if on_delivery:
            on_delivery(None, None)  # 전달 성공

    def poll(self, t):
        pass

    def flush(self, t=None):
        return 0


class BrokenProducer(FakeProducer):
    """전달이 전부 실패하는 프로듀서 — 브로커에 못 붙는 상황."""

    def produce(self, topic, key, value, on_delivery=None):
        if on_delivery:
            on_delivery("Connect failed", None)

    def flush(self, t=None):
        return 3  # 미확인 잔량


def _mini_csv(path, rows):
    lines = ["company|title|link|published|category|category_str|reporter|article"]
    lines += ["|".join(r) for r in rows]
    path.write_text("\n".join(lines), encoding="utf-8")


def test_run_sends_dedups_and_resumes(tmp_path, monkeypatch):
    rows = [
        ["동아일보", "기사1", "https://a.com/1", "2025-01-01 10:00", "문화", "", "김기자", "b"],
        ["동아일보", "기사1 재수록", "https://a.com/1", "2025-01-01 10:00", "문화", "", "김기자", "b"],  # 링크 중복
        ["동아일보", "기사2", "https://a.com/2", "2025-01-01 11:00", "문화", "", "김기자", "b"],
        ["동아일보", "깨진행", "no-url", "2025-01-01 12:00", "", "", "", "b"],  # 부적합
        ["동아일보", "기사3", "https://a.com/3", "2025-01-01 13:00", "문화", "", "김기자", "b"],
    ]
    _mini_csv(tmp_path / "ssafy_dataset_news_mini.csv", rows)
    monkeypatch.setattr(ds, "DATASET_DIR", str(tmp_path))
    monkeypatch.setattr(ds, "FILES", ["mini"])
    monkeypatch.setattr(ds, "RATE_PER_SEC", 100000.0)
    ckpt = str(tmp_path / "ckpt.sqlite")

    p1 = FakeProducer()
    stats = ds.run(send=True, limit=2, checkpoint_path=ckpt, producer=p1)
    assert stats == {"sent": 2, "dedup": 1, "invalid": 0}  # 기사1, (중복 스킵), 기사2

    p2 = FakeProducer()
    stats = ds.run(send=True, checkpoint_path=ckpt, producer=p2)  # 이어서 재개
    assert stats == {"sent": 1, "dedup": 0, "invalid": 1}  # 깨진행 스킵, 기사3만
    assert len(p2.messages) == 1

    p3 = FakeProducer()
    stats = ds.run(send=True, checkpoint_path=ckpt, producer=p3)  # 완주 후 재실행
    assert stats == {"sent": 0, "dedup": 0, "invalid": 0}
    assert p3.messages == []


def test_run_refuses_to_checkpoint_undelivered(tmp_path, monkeypatch):
    import pytest, sqlite3
    rows = [["동아일보", "기사1", "https://a.com/1", "2025-01-01 10:00", "문화", "", "김기자", "b"]]
    _mini_csv(tmp_path / "ssafy_dataset_news_mini.csv", rows)
    monkeypatch.setattr(ds, "DATASET_DIR", str(tmp_path))
    monkeypatch.setattr(ds, "FILES", ["mini"])
    monkeypatch.setattr(ds, "RATE_PER_SEC", 100000.0)
    ckpt = str(tmp_path / "ckpt.sqlite")

    with pytest.raises(RuntimeError, match="체크포인트를 기록하지 않았습니다"):
        ds.run(send=True, checkpoint_path=ckpt, producer=BrokenProducer())

    # 체크포인트에 거짓 완료가 남지 않아 재실행하면 다시 보낸다
    good = FakeProducer()
    stats = ds.run(send=True, checkpoint_path=ckpt, producer=good)
    assert stats["sent"] == 1 and len(good.messages) == 1


def test_resume_counter_continues_from_checkpoint(tmp_path, monkeypatch, capsys):
    rows = [
        ["동아일보", "기사1", "https://a.com/1", "2025-01-01 10:00", "문화", "", "김기자", "b"],
        ["동아일보", "기사2", "https://a.com/2", "2025-01-01 11:00", "문화", "", "김기자", "b"],
    ]
    _mini_csv(tmp_path / "ssafy_dataset_news_mini.csv", rows)
    monkeypatch.setattr(ds, "DATASET_DIR", str(tmp_path))
    monkeypatch.setattr(ds, "FILES", ["mini"])
    monkeypatch.setattr(ds, "RATE_PER_SEC", 100000.0)
    ckpt = str(tmp_path / "ckpt.sqlite")

    ds.run(send=True, limit=1, checkpoint_path=ckpt, producer=FakeProducer(), verbose=True)
    assert "[1]" in capsys.readouterr().out

    ds.run(send=True, checkpoint_path=ckpt, producer=FakeProducer(), verbose=True)
    assert "[2]" in capsys.readouterr().out  # 1부터가 아니라 이어서
