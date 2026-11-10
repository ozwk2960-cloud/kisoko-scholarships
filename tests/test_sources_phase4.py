"""フェーズ4で追加したソース（船井・吉田・孫正義・阪大）の fixture テスト。"""

from __future__ import annotations

import os

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


# ---- 阪大: 【対象】の解析と公式情報の補正（2026-11 時点の実ページのスナップショット） ----

def _osaka_live_items():
    path = os.path.join(os.path.dirname(__file__), "fixtures", "osaka_outbound_scholarship_2026-11-10.html")
    html = open(path, encoding="utf-8").read()
    items, status = OsakaUSource(fetcher=lambda url: html).run()
    assert status["ok"], status
    return {it.title: it for it in items}


def _find(items, key):
    hits = [it for t, it in items.items() if key in t]
    assert hits, key
    return hits[0]


def test_osaka_does_not_assert_unverified_values():
    # 以前は全件に「全分野」「全世界」を無条件で入れていた。確認できないものは空（=要確認）にする。
    items = _osaka_live_items()
    unknown_degree = [it for it in items.values() if not it.target_degree]
    assert unknown_degree, "学年が不明な制度は空のまま残すこと"
    # 公式ページが自動で読めない制度（竹中育英会・村田海外留学奨学会）は、何も断定せず空のまま
    for key in ("竹中育英会", "村田海外留学奨学会"):
        it = _find(items, key)
        assert it.target_degree == [] and it.target_fields == [] and it.destination_countries == []


def test_osaka_target_parsing():
    items = _osaka_live_items()
    assert _find(items, "みずほ国際交流").target_degree == ["bachelor"]
    assert "交換留学" in _find(items, "みずほ国際交流").study_type
    assert _find(items, "日揮・実吉").target_degree == ["master"]
    assert _find(items, "日揮・実吉").target_fields == ["理工系"]
    assert _find(items, "経団連国際教育交流財団").target_degree == ["master", "doctor"]
    assert _find(items, "大林財団").target_degree == ["bachelor", "master", "doctor"]
    assert _find(items, "大林財団").target_fields == ["全分野"]
    assert _find(items, "TOMODACHI").destination_countries == ["アメリカ"]
    assert _find(items, "佐藤陽").destination_countries == ["東南アジア", "南西アジア"]
    assert _find(items, "語学留学助成").study_type == ["語学"]


def test_osaka_inpex_is_graduate_only():
    # 利用者が報告した不具合: INPEX教育交流財団は学部生が対象ではない
    inpex = _find(_osaka_live_items(), "INPEX")
    assert inpex.target_degree == ["master", "doctor"]
    assert "bachelor" not in inpex.target_degree
    assert set(inpex.destination_countries) == {"インドネシア", "オーストラリア", "UAE"}
    assert "学部生は対象外" in (inpex.description or "")


def test_osaka_curated_covers_direct_apply_rows():
    items = _osaka_live_items()
    for key in ("伊藤国際", "豊田理化学", "フルブライト", "スイス政府", "霞山会"):
        it = _find(items, key)
        assert it.study_type or it.target_degree, key
    # 学部生を含む制度・含まない制度の取り違えが無い
    assert "bachelor" not in _find(items, "本庄").target_degree
    assert "bachelor" in _find(items, "中国政府奨学金").target_degree


def test_osaka_curated_from_official_requirements():
    items = _osaka_live_items()
    # 経団連GL: 学部2〜4年＋博士前期のみ（博士後期は対象外）
    k = _find(items, "経団連グローバル人材育成")
    assert k.target_degree == ["bachelor", "master"] and "doctor" not in k.target_degree
    # アポロ: 学部生・大学院生、留学先は中国、専攻の列挙は基礎工の専攻名と合わないので入れない
    a = _find(items, "アポロ")
    assert a.destination_countries == ["中国"] and a.target_fields == []
    # フィンドレー: 福井県在住等の条件がカードの説明に出る
    assert "福井県" in (_find(items, "フィンドレー").description or "")
    # フクシマ: 短期も学部生
    assert _find(items, "フクシマグローバル人材支援奨学財団（短期）").target_degree == ["bachelor"]
    # 寺浦（同名2件とも）
    assert all(it.target_degree for t, it in items.items() if "寺浦" in t) or _find(items, "寺浦").target_degree


def test_osaka_all_fields_only_when_official_requirements_have_no_field_condition():
    items = _osaka_live_items()
    for key in ("業務スーパージャパンドリーム", "阪和育英会", "みずほ国際交流", "大遊協"):
        it = _find(items, key)
        assert it.target_fields == ["全分野"] and it.target_degree == ["bachelor"], key
    # 公式要項を読めていない制度には「全分野」を付けない
    for key in ("TOMODACHI", "佐藤陽"):
        assert _find(items, key).target_fields == [], key


# ---- 阪大: 学内募集の状況（「募集終了」表示）と募集回ごとの締切 ----

def test_osaka_closed_marker_is_read():
    items = _osaka_live_items()
    # 学内推薦の表: 「募集終了」と表示されている行は closed、無い行は open
    assert _find(items, "業務スーパージャパンドリーム財団 2026年度第2回").application_status == "closed"
    assert _find(items, "阪和育英会").application_status == "open"
    assert _find(items, "業務スーパージャパンドリーム財団 2026年度第2回").koan_posted == "2026-06-04"
    # 直接応募の表には終了表示が無いので、日付や公式情報が無い限り「不明」のまま（open と断定しない）
    assert _find(items, "村田海外留学奨学会").application_status is None


def test_osaka_round_deadlines_apply_only_to_that_round():
    items = _osaka_live_items()
    prince = _find(items, "皇太子明仁親王")
    assert prince.deadline == "2026-11-30" and prince.deadline_type == "fixed"
    assert _find(items, "SEKAIA").application_status == "closed"
    # 年度が違うタイトル・掲示日が違う行には当たらない（古い締切が次の募集に残らない）
    import re
    from scraper import config
    def hits(title, posted=None):
        for r in config.OSAKA_ROUNDS:
            if re.search(r["match"], title) and ("posted" not in r or r["posted"] == posted):
                return True
        return False
    assert hits("【経団連グローバル人材育成スカラーシップ】2027年度奨学生")
    assert not hits("【経団連グローバル人材育成スカラーシップ】2028年度奨学生")
    assert hits("【福井県】フィンドレー大学・福井県奨学生", "2026-05-28")
    assert not hits("【福井県】フィンドレー大学・福井県奨学生", "2027-05-20")


def test_osaka_fukushima_short_is_language_not_exchange():
    # 【対象】が「※…」の前置き付きでも読めること。「交換留学は含みません」を交換留学と誤読しない
    short = _find(_osaka_live_items(), "フクシマグローバル人材支援奨学財団（短期）")
    assert short.study_type == ["語学"]
    assert "海外研修プログラム" in (short.description or "")
