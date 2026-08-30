from __future__ import annotations

from scraper.merge import merge
from scraper.models import Scholarship


def mk(id_, source="JASSO", title="t", deadline=None):
    return Scholarship(
        id=id_, source=source, source_url="https://x.test/", title=title,
        provider="p", category="public", deadline=deadline,
    )


def test_success_sets_first_and_last_seen():
    prev = {
        "generated_at": "2026-08-01T00:00:00Z",
        "source_status": [],
        "scholarships": [
            {"id": "jasso-a", "source": "JASSO", "source_url": "https://x.test/",
             "title": "t", "provider": "p", "category": "public",
             "first_seen": "2026-07-01", "last_seen": "2026-07-31"},
        ],
    }
    out = merge(
        results={"JASSO": [mk("jasso-a"), mk("jasso-b")]},
        statuses=[{"source": "JASSO", "ok": True, "count": 2}],
        previous=prev, today="2026-08-30",
    )
    by_id = {s["id"]: s for s in out["scholarships"]}
    assert by_id["jasso-a"]["first_seen"] == "2026-07-01"   # 引き継ぎ
    assert by_id["jasso-a"]["last_seen"] == "2026-08-30"
    assert by_id["jasso-b"]["first_seen"] == "2026-08-30"   # 新規


def test_failed_source_keeps_previous_data():
    prev = {
        "generated_at": "2026-08-01T00:00:00Z",
        "source_status": [],
        "scholarships": [
            {"id": "tobitate-x", "source": "トビタテ", "source_url": "https://x.test/",
             "title": "t", "provider": "p", "category": "public",
             "first_seen": "2026-06-01", "last_seen": "2026-08-29"},
        ],
    }
    out = merge(
        results={"トビタテ": []},
        statuses=[{"source": "トビタテ", "ok": False, "error": "HTTP 503"}],
        previous=prev, today="2026-08-30",
    )
    assert [s["id"] for s in out["scholarships"]] == ["tobitate-x"]
    st = {s["source"]: s for s in out["source_status"]}["トビタテ"]
    assert st["ok"] is False
    assert st["stale_since"] == "2026-08-30"
    # last_seen は据え置き（今日にしない）
    assert out["scholarships"][0]["last_seen"] == "2026-08-29"


def test_zero_items_when_previous_had_data_is_treated_as_failure():
    prev = {
        "generated_at": "x", "source_status": [],
        "scholarships": [
            {"id": "jasso-a", "source": "JASSO", "source_url": "https://x.test/",
             "title": "t", "provider": "p", "category": "public",
             "first_seen": "2026-01-01", "last_seen": "2026-08-29"},
        ],
    }
    out = merge(
        results={"JASSO": []},
        statuses=[{"source": "JASSO", "ok": True, "count": 0}],
        previous=prev, today="2026-08-30",
    )
    st = {s["source"]: s for s in out["source_status"]}["JASSO"]
    assert st["ok"] is False
    assert "0 items" in st["error"]
    assert [s["id"] for s in out["scholarships"]] == ["jasso-a"]


def test_dedup_by_triple():
    out = merge(
        results={"JASSO": [mk("id1", title="同じ", deadline="2026-10-01"),
                           mk("id2", title="同じ", deadline="2026-10-01")]},
        statuses=[{"source": "JASSO", "ok": True, "count": 2}],
        previous=None, today="2026-08-30",
    )
    assert len(out["scholarships"]) == 1


def test_output_is_sorted():
    out = merge(
        results={"JASSO": [mk("jasso-z"), mk("jasso-a")]},
        statuses=[{"source": "JASSO", "ok": True, "count": 2}],
        previous=None, today="2026-08-30",
    )
    ids = [s["id"] for s in out["scholarships"]]
    assert ids == sorted(ids)
