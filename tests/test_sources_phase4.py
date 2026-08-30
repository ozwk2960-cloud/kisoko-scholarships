"""フェーズ4で追加したソース（船井・吉田・孫正義・阪大）の fixture テスト。"""

from __future__ import annotations

from scraper.models import VALID_CATEGORIES, VALID_DEADLINE_TYPES
from scraper.sources.funai import FunaiSource
from scraper.sources.masason import MasasonSource
from scraper.sources.osaka_u import OsakaUSource
from scraper.sources.yoshida import YoshidaSource

REQUIRED = ("id", "source", "source_url", "title", "provider", "category")


def _check(items):
    assert items
    ids = set()
    for it in items:
        d = it.to_dict()
        for f in REQUIRED:
            assert d[f], f"{f} 空: {d.get('id')}"
        assert d["id"] not in ids, f"id 重複: {d['id']}"
        ids.add(d["id"])
        assert d["category"] in VALID_CATEGORIES
        assert d["deadline_type"] in VALID_DEADLINE_TYPES
        assert d["source_url"].startswith("http")
        it.validate_light()


def test_funai(fixture_fetcher):
    items, status = FunaiSource(fetcher=fixture_fetcher).run()
    assert status["ok"], status
    _check(items)
    by_id = {it.id: it for it in items}
    phd = by_id["funai-phd"]
    assert phd.deadline == "2026-09-30"          # 応募期間から動的に取得
    assert phd.deadline_type == "fixed"
    assert phd.target_degree == ["doctor"]
    assert phd.requires_university_nomination is False
    assert "米ドル" in (phd.amount_text or "")
    assert by_id["funai-bachelor"].target_degree == ["bachelor"]


def test_yoshida(fixture_fetcher):
    items, status = YoshidaSource(fetcher=fixture_fetcher).run()
    assert status["ok"], status
    _check(items)
    it = items[0]
    assert "2027年度採用" in it.title             # ページから対象年度を取得
    assert it.deadline is None                    # 締切は PDF 側
    assert it.deadline_type == "annual"
    assert set(it.target_degree) == {"master", "doctor"}


def test_masason(fixture_fetcher):
    items, status = MasasonSource(fetcher=fixture_fetcher).run()
    assert status["ok"], status
    _check(items)
    it = items[0]
    assert "第10期" in it.title                   # top ニュースから期を取得
    assert "現在は募集していません" in it.tags       # requirements ページの「今期の募集は終了」
    assert it.deadline_type == "unknown"


def test_osaka(fixture_fetcher):
    items, status = OsakaUSource(fetcher=fixture_fetcher).run()
    assert status["ok"], status
    _check(items)
    assert len(items) >= 20

    # セクションで学内推薦フラグが分かれている
    noms = {it.requires_university_nomination for it in items}
    assert True in noms and False in noms

    # 直接スクレイプ済みの制度は除外
    for it in items:
        assert "JASSO" not in it.title and "トビタテ" not in it.title
        assert "大阪大学" in it.eligible_universities

    # 過年度（掲示日が古い）の行は落ちている
    import re
    for it in items:
        m = re.search(r"掲示日 (\d{4})-", it.application_period_text or "")
        assert m and int(m.group(1)) >= 2025


def test_osaka_internal_links_fall_back(fixture_fetcher):
    items, _ = OsakaUSource(fetcher=fixture_fetcher).run()
    for it in items:
        assert "my.osaka-u.ac.jp" not in it.source_url
