"""各ソースを fixture 経由で parse し、件数と必須項目を検証する（ネットワーク非依存）。"""

from __future__ import annotations

from scraper.models import VALID_CATEGORIES, VALID_DEADLINE_TYPES
from scraper.sources.jasso import JassoSource
from scraper.sources.tobitate import TobitateSource

REQUIRED = ("id", "source", "source_url", "title", "provider", "category")


def _check_common(items):
    assert items, "1件も抽出できていない"
    ids = set()
    for it in items:
        d = it.to_dict()
        for f in REQUIRED:
            assert d[f], f"必須フィールド {f} が空: {d.get('id')}"
        assert d["id"] not in ids, f"id 重複: {d['id']}"
        ids.add(d["id"])
        assert d["category"] in VALID_CATEGORIES
        assert d["deadline_type"] in VALID_DEADLINE_TYPES
        assert d["source_url"].startswith("http")
        it.validate_light()


def test_jasso_parse(fixture_fetcher):
    items, status = JassoSource(fetcher=fixture_fetcher).run()
    assert status["ok"], status
    _check_common(items)

    by_id = {it.id: it for it in items}
    # 学部 2027 は募集中（締切あり・「募集していません」タグなし）
    g27 = by_id["jasso-gakubu-2027"]
    assert g27.deadline == "2026-10-01"
    assert g27.deadline_type == "fixed"
    assert "現在は募集していません" not in g27.tags
    assert g27.target_degree == ["bachelor"]

    # 大学院 2026 は募集終了
    d26 = by_id["jasso-daigakuin-2026"]
    assert d26.deadline == "2025-10-09"
    assert "現在は募集していません" in d26.tags
    assert set(d26.target_degree) == {"master", "doctor"}


def test_jasso_skips_placeholder_year_page(fixture_fetcher):
    """h1 空・日程表なしの未公開ページはエントリ化しない。"""
    src = JassoSource(fetcher=fixture_fetcher)
    prog = {"key": "daigakuin", "label": "大学院学位取得型"}
    empty_html = fixture_fetcher_or_file("jasso_daigakuin_2027_empty.html")
    src.fetch = lambda url: empty_html
    result = src._parse_year_page(prog, 2027, "https://example.com/2027.html")
    assert result is None


def test_tobitate_parse(fixture_fetcher):
    items, status = TobitateSource(fetcher=fixture_fetcher).run()
    assert status["ok"], status
    _check_common(items)
    assert len(items) == 1
    it = items[0]
    assert "大学生等対象" in it.title
    assert "第18期" in it.title          # UV ページから期を取得
    assert it.deadline is None           # HTML から締切日は取らない
    assert it.amount_monthly_jpy == 60000
    # 第18期は募集終了済み
    assert "現在は募集していません" in it.tags


# --- helper ---
def fixture_fetcher_or_file(name: str) -> str:
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "fixtures", name), encoding="utf-8", errors="replace") as fh:
        return fh.read()
