import datetime as dt
import json

from jobs import publish_clustering as pc

UTC = dt.timezone.utc


def _row(cluster_id, link, minute, label=None, stance=None):
    return {
        "cluster_id": cluster_id, "category": "정치",
        "fact_summary": "제목", "common_facts_briefing": "본문 앞부분",
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
    assert "(샘플 브리핑)" in msg["commonFactsBriefing"]
    per_group = {}
    for a in msg["articles"]:
        assert a["viewpointGroupLabel"].startswith("[샘플]")
        assert a["stance"] in ("positive", "neutral", "negative")
        per_group.setdefault(a["viewpointGroupLabel"], set()).add(a["stance"])
    assert all(len(v) == 1 for v in per_group.values())  # 한 관점 그룹은 성향 하나


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
