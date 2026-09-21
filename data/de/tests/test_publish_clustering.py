import datetime as dt
import json

from jobs import publish_clustering as pc

UTC = dt.timezone.utc


def _row(cluster_id, link, minute, label=None, stance=None):
    return {
        "cluster_id": cluster_id, "category": "정치",
        "fact_summary": "제목", "common_facts_briefing": ["첫째 사실", "둘째 사실"],
        "clustered_at": dt.datetime(2026, 9, 8, 19, 43, 37, tzinfo=UTC),
        "link": link, "viewpoint_group_label": label, "stance": stance,
        "publisher_id": "yonhap",
        "published_at": dt.datetime(2026, 9, 8, 1, minute, tzinfo=UTC),
        "article_id": "sha256:" + str(minute), "issue_size": 2, "publishers": 2,
        "hot_score": 1.0, "is_representative": minute == 0,
    }


def test_clustered_at_carries_korean_offset():
    # BE 는 오프셋 있는 ISO-8601 을 요구한다. UTC 19:43 은 한국 다음날 04:43
    assert pc.to_kst_iso(dt.datetime(2026, 9, 8, 19, 43, 37, tzinfo=UTC)) == "2026-09-09T04:43:37+09:00"


def test_message_shape_matches_be_spec_and_orders_articles_by_time():
    rows = [_row(7, "https://a/2", 5), _row(7, "https://a/1", 0)]
    msg = pc.build_message(rows)
    assert set(msg) == {"clusterId", "category", "factSummary",
                        "commonFactsBriefing", "clusteredAt", "articles"}
    assert msg["clusterId"] == 7
    assert [a["link"] for a in msg["articles"]] == ["https://a/1", "https://a/2"]


def test_without_mock_flag_viewpoint_fields_stay_empty():
    # 표에는 사실만 담는다. 목업을 실수로 보내지 않게 옵션 없이는 빈 값이 그대로 나간다
    msg = pc.build_message([_row(7, "https://a/1", 0)])
    assert msg["articles"][0]["stance"] is None
    assert msg["articles"][0]["viewpointGroupLabel"] is None
    assert "(샘플" not in msg["factSummary"]


def test_mock_flag_fills_viewpoints_with_visible_marker_and_one_stance_per_group():
    rows = [_row(7, f"https://a/{i}", i) for i in range(8)]
    msg = pc.build_message(rows, mock=True)
    assert "(샘플 요약)" in msg["factSummary"]
    assert msg["commonFactsBriefing"] == ["첫째 사실", "둘째 사실", "(샘플 브리핑)"]
    per_group = {}
    for a in msg["articles"]:
        assert a["viewpointGroupLabel"].startswith("[샘플]")
        assert a["stance"] in ("positive", "neutral", "negative")
        per_group.setdefault(a["viewpointGroupLabel"], set()).add(a["stance"])
    assert all(len(v) == 1 for v in per_group.values())  # 한 관점 그룹은 성향 하나


def test_briefing_goes_out_as_a_list_of_sentences():
    # BE 가 List<String> 으로 받는다. DS2 가 문장 리스트를 주므로 합치지 않고 그대로 넘긴다
    msg = pc.build_message([_row(7, "https://a/1", 0)])
    assert msg["commonFactsBriefing"] == ["첫째 사실", "둘째 사실"]


def test_missing_required_counts_empty_briefing_list_as_missing():
    # [] 는 (None, "") 에 안 걸려 값이 있는 것으로 보였다
    rows = [_row(7, "https://a/1", 0, label="A-1 경제적 기대 효과", stance="positive")]
    rows[0]["common_facts_briefing"] = []
    assert pc.missing_required(pc.build_message(rows)) == ["commonFactsBriefing"]


class FakeProducer:
    def __init__(self, fail=False):
        self.sent = []
        self._fail = fail

    def produce(self, topic, key, value, on_delivery=None):
        self.sent.append((topic, key, json.loads(value)))
        if on_delivery:
            on_delivery("실패" if self._fail else None, None)

    def poll(self, timeout):
        pass

    def flush(self, timeout=None):
        return 0


def test_publish_uses_cluster_id_string_as_key():
    rows = {7: [_row(7, "https://a/1", 0)], 9: [_row(9, "https://b/1", 0)]}
    messages = [pc.build_message(v) for v in rows.values()]
    producer = FakeProducer()
    assert pc.publish(messages, producer=producer, rate=0) == 2
    assert [k for _, k, _ in producer.sent] == ["7", "9"]  # 문자열 key
    assert {t for t, _, _ in producer.sent} == {"news.clustering.completed"}


def test_publish_raises_when_delivery_fails():
    import pytest
    producer = FakeProducer(fail=True)
    with pytest.raises(RuntimeError):
        pc.publish([pc.build_message([_row(7, "https://a/1", 0)])], producer=producer, rate=0)


def test_missing_required_lists_empty_be_fields():
    # 목업 없이 보낼 수 있는지 미리 알려준다. BE 는 여덟 필드를 전부 필수로 요구한다
    msg = pc.build_message([_row(7, "https://a/1", 0)])
    assert pc.missing_required(msg) == ["articles[].viewpointGroupLabel", "articles[].stance"]


def test_missing_required_empty_when_ds2_filled_everything():
    rows = [_row(7, "https://a/1", 0, label="A-1 경제적 기대 효과", stance="positive")]
    assert pc.missing_required(pc.build_message(rows)) == []


# --- 이슈 번호 이어붙이기 (S15P21E105-129) ---------------------------------

def _cluster(cluster_id, article_ids):
    """stable_ids 가 보는 최소 모양 — 이슈 하나와 그 기사들."""
    return [{"cluster_id": cluster_id, "article_id": a} for a in article_ids]


def test_issue_id_carries_over_when_most_articles_came_from_one_previous_issue():
    # 실제 사고 재현: 09-18 에 29388 로 나간 기사 3건이 09-19 에 31214 로 다시 묶였다.
    # 어제 번호를 그대로 써야 BE 가 같은 이슈로 갱신한다
    history = {"a": 29388, "b": 29388, "c": 29388, "d": 29388}
    grouped = {31214: _cluster(31214, ["a", "b", "c"])}
    assert pc.stable_ids(grouped, history) == {31214: 29388}


def test_issue_id_stays_put_when_run_again_on_its_own_result():
    # 발행은 하루 세 번 돈다. 두 번째 실행이 첫 번째 결과를 보고 번호를 바꾸면 안 된다
    history = {"a": 29388, "b": 29388, "c": 29388}
    grouped = {31214: _cluster(31214, ["a", "b", "c"])}
    first = pc.stable_ids(grouped, history)
    after = dict(history)
    after.update({a: first[31214] for a in ["a", "b", "c"]})
    assert pc.stable_ids(grouped, after) == first


def test_one_previous_id_goes_to_the_cluster_that_shares_more_articles():
    # 이슈가 둘로 쪼개지면 번호는 하나뿐이다. 많이 겹치는 쪽이 가져가고 나머지는 제 번호를 쓴다
    history = {"a": 100, "b": 100, "c": 100, "d": 100, "e": 100}
    grouped = {7: _cluster(7, ["a", "b", "c"]), 8: _cluster(8, ["d", "e"])}
    assert pc.stable_ids(grouped, history) == {7: 100, 8: 8}


def test_without_history_every_cluster_keeps_its_own_id():
    # 기억 파일이 없거나 비어 있으면 지금과 똑같이 동작해야 한다
    grouped = {7: _cluster(7, ["a"]), 8: _cluster(8, ["b"])}
    assert pc.stable_ids(grouped, {}) == {7: 7, 8: 8}


def test_a_single_shared_article_is_not_enough_to_take_the_id():
    # 기사 한 건 겹쳤다고 이어붙이면 남의 이슈를 집어삼킨다. DS 승계와 같은 문턱을 쓴다
    history = {"a": 100}
    grouped = {7: _cluster(7, ["a", "x", "y", "z"])}
    assert pc.stable_ids(grouped, history) == {7: 7}


def test_minority_vote_does_not_take_the_id():
    # 겹친 기사가 여러 이슈에서 왔고 최다가 과반이 아니면 새 이슈로 본다
    history = {"a": 100, "b": 100, "c": 200, "d": 300, "e": 400}
    grouped = {7: _cluster(7, ["a", "b", "c", "d", "e"])}
    assert pc.stable_ids(grouped, history) == {7: 7}


def test_does_not_steal_an_id_another_cluster_is_already_using_today():
    # 오늘 29388 군집이 따로 살아 있는데 다른 군집이 그 번호를 가져가면 키가 겹쳐
    # BE 에서 두 이슈가 서로를 덮어쓴다
    history = {"a": 29388, "b": 29388}
    grouped = {31214: _cluster(31214, ["a", "b"]), 29388: _cluster(29388, ["z"])}
    assert pc.stable_ids(grouped, history) == {31214: 31214, 29388: 29388}


def test_resolved_ids_never_repeat():
    # 어떤 경우에도 한 번 발행에 같은 키가 둘 나오면 안 된다
    history = {"a": 100, "b": 100, "c": 100, "d": 100}
    grouped = {7: _cluster(7, ["a", "b"]), 8: _cluster(8, ["c", "d"]), 100: _cluster(100, ["z"])}
    resolved = pc.stable_ids(grouped, history)
    assert len(set(resolved.values())) == len(resolved)


def test_recent_ids_reads_back_a_few_days_and_lets_today_win():
    # 오늘 이미 정한 번호가 어제 것보다 우선한다 — 하루 안에서 번호가 흔들리지 않게
    issue_map = {"2026-09-17": {"a": 1}, "2026-09-18": {"a": 2}, "2026-09-19": {"a": 3}}
    assert pc.recent_ids(issue_map, "2026-09-19", lookback=3)["a"] == 3


def test_recent_ids_ignores_days_beyond_the_lookback():
    issue_map = {"2026-09-10": {"old": 1}, "2026-09-19": {"new": 2}}
    history = pc.recent_ids(issue_map, "2026-09-20", lookback=3)
    assert "old" not in history and history["new"] == 2


def test_issue_map_round_trips_and_drops_old_days(tmp_path):
    path = tmp_path / "publish_issue_map.json"
    pc.save_issue_map(str(path), {"2026-09-01": {"a": 1}, "2026-09-20": {"b": 2}},
                      day="2026-09-20", lookback=3)
    assert pc.load_issue_map(str(path)) == {"2026-09-20": {"b": 2}}


def test_missing_issue_map_reads_as_empty(tmp_path):
    # 파일이 없어도 발행은 계속돼야 한다
    assert pc.load_issue_map(str(tmp_path / "nope.json")) == {}
