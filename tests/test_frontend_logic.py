"""public/index.html の絞り込みロジック（MATCH-LOGIC 区間）を node で実行して検証する。

ブラウザなしで「学部 × システム × 交換留学 × 推薦不要」のような実際の検索を再現し、
確認済みの不一致（例: 院生のみの制度）が必ず除外されることを守る回帰テスト。
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, "public", "index.html")

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node が無い環境ではスキップ")


def _js_prelude() -> str:
    html = open(INDEX, encoding="utf-8").read()
    region = re.search(r"/\* ===== MATCH-LOGIC:START.*?MATCH-LOGIC:END ===== \*/", html, re.S)
    assert region, "MATCH-LOGIC 区間が見つかりません"
    consts = []
    for name in ("REGION_KEYWORDS", "FIELD_KEYWORDS"):
        m = re.search(r"const %s = \{.*?\n\};" % name, html, re.S)
        assert m, name
        consts.append(m.group(0))
    return "\n".join(consts) + "\n" + region.group(0)


def run_filter(items, today="2026-11-10", **cond):
    """条件 cond（state の上書き）で絞り込み、残ったタイトル一覧を返す。"""
    state = {"degree": None, "field": None, "region": "", "types": [], "nomination": "any",
             "osakaOnly": False, "hidePast": False, "soonOnly": False, "showUnverified": False, "query": ""}
    state.update(cond)
    script = _js_prelude() + """
const input = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const state = Object.assign({}, input.state, { types: new Set(input.state.types) });
function daysLeftOf(it) {
  if (!it.deadline) return null;
  return Math.round((new Date(it.deadline + "T00:00:00") - new Date(input.today + "T00:00:00")) / 86400000);
}
const out = input.items.filter(it => passesHardFilters(it, daysLeftOf(it))).map(it => it.title);
const cls = Object.fromEntries(input.items.map(it => [it.title, classify(it, daysLeftOf(it))]));
const unv = Object.fromEntries(input.items.map(it => [it.title, unverifiedConditions(it)]));
console.log(JSON.stringify({ out, unv, cls }));
"""
    p = subprocess.run(["node", "-e", script], input=json.dumps({"items": items, "state": state, "today": today}),
                       capture_output=True, text=True, check=True)
    return json.loads(p.stdout)


def item(title, **kw):
    base = {"title": title, "target_degree": [], "target_fields": [], "destination_countries": [],
            "study_type": [], "requires_university_nomination": None, "eligible_universities": [],
            "description": "", "provider": "", "tags": []}
    base.update(kw)
    return base


GRAD_ONLY = item("院生のみ", target_degree=["master", "doctor"], target_fields=["全分野"],
                 destination_countries=["インドネシア"], requires_university_nomination=False)
UG_EXCHANGE = item("学部交換", target_degree=["bachelor"], study_type=["交換留学"],
                   requires_university_nomination=False)
UNKNOWN = item("未確認", requires_university_nomination=False)


def test_confirmed_degree_mismatch_is_excluded():
    # 利用者が報告した不具合: 学部を選んだのに院生限定の制度（INPEX 等）が出てきた
    r = run_filter([GRAD_ONLY, UG_EXCHANGE, UNKNOWN], degree="bachelor")
    assert "院生のみ" not in r["out"]
    assert "学部交換" in r["out"]


def test_unknown_is_hidden_by_default_and_shown_on_request():
    # 既定では「条件に合うと確認できたもの」だけ。未確認は区分だけ返り、トグルで表示できる
    r = run_filter([UG_EXCHANGE, UNKNOWN], degree="bachelor")
    assert r["out"] == ["学部交換"]
    assert r["cls"]["未確認"] == "unverified"
    r = run_filter([UG_EXCHANGE, UNKNOWN], degree="bachelor", showUnverified=True)
    assert set(r["out"]) == {"学部交換", "未確認"}
    assert r["unv"]["未確認"] == ["学年・課程"]


def test_study_type_mismatch_is_excluded():
    degree_only = item("学位取得のみ", target_degree=["bachelor"], study_type=["学位取得"])
    r = run_filter([degree_only, UG_EXCHANGE], degree="bachelor", types=["交換留学"])
    assert r["out"] == ["学部交換"]


def test_generic_field_matches_any_kiso_field():
    sci = item("理工系", target_degree=["bachelor"], target_fields=["理工系"])
    hum = item("人文系", target_degree=["bachelor"], target_fields=["人文社会科学"])
    r = run_filter([sci, hum], field="システム")
    assert r["out"] == ["理工系"]


def test_region_mismatch_and_all_world():
    us = item("米国", destination_countries=["アメリカ"])
    world = item("全世界", destination_countries=["全世界"])
    r = run_filter([us, world, GRAD_ONLY], region="欧州")
    assert r["out"] == ["全世界"]
    # インドネシアは「アジア」
    assert "院生のみ" in run_filter([GRAD_ONLY], region="アジア")["out"]


def test_nomination_none_requires_confirmed_false():
    needs = item("推薦要", requires_university_nomination=True)
    unk = item("推薦不明", requires_university_nomination=None)
    free = item("推薦不要", requires_university_nomination=False)
    r = run_filter([needs, unk, free], nomination="none")
    assert r["out"] == ["推薦不要"]


def test_closed_items_are_hidden_when_requested():
    closed_by_status = item("学内終了", target_degree=["bachelor"], application_status="closed")
    closed_by_deadline = item("締切過ぎ", target_degree=["bachelor"], deadline="2026-10-01", deadline_type="fixed")
    open_one = item("募集中", target_degree=["bachelor"], application_status="open")
    future = item("締切前", target_degree=["bachelor"], deadline="2026-12-01", deadline_type="fixed")
    items = [closed_by_status, closed_by_deadline, open_one, future]
    assert set(run_filter(items, hidePast=True)["out"]) == {"募集中", "締切前"}
    assert len(run_filter(items, hidePast=False)["out"]) == 4


def test_soon_only_needs_known_deadline_within_30_days():
    soon = item("締切間近", deadline="2026-11-30", deadline_type="fixed")
    far = item("まだ先", deadline="2027-03-01", deadline_type="fixed")
    unknown = item("締切不明")
    r = run_filter([soon, far, unknown], soonOnly=True)
    assert r["out"] == ["締切間近"]


def test_osaka_only_means_listed_on_osaka_page():
    on_osaka = item("阪大掲載", source="大阪大学")
    national = item("全国制度", source="JASSO", eligible_universities=["全国"])
    assert run_filter([on_osaka, national], osakaOnly=True)["out"] == ["阪大掲載"]
    assert len(run_filter([on_osaka, national])["out"]) == 2


def _real_items():
    path = os.path.join(ROOT, "public", "scholarships.json")
    if not os.path.exists(path):
        pytest.skip("scholarships.json 未生成")
    return json.load(open(path, encoding="utf-8"))["scholarships"]


def test_user_scenario_on_real_data():
    """利用者が実際に試した検索を、現行の scholarships.json で再現する。"""
    items = _real_items()
    r = run_filter(items, degree="bachelor", field="システム", types=["交換留学"], nomination="none")
    assert not any("INPEX" in t for t in r["out"])
    by_title = {i["title"]: i for i in items}
    for t in r["out"]:
        it = by_title[t]
        assert "bachelor" in it["target_degree"], t          # 学部が確認できたものだけが並ぶ
        assert "交換留学" in it["study_type"], t
        assert it["requires_university_nomination"] is False, t


def test_language_search_returns_only_language_programs():
    """「語学」で絞ると、語学と確認できた制度だけが並ぶ（利用者の指摘②）。"""
    items = _real_items()
    r = run_filter(items, types=["語学"], hidePast=True)
    assert r["out"], "語学の制度が1件も出ない"
    by_title = {i["title"]: i for i in items}
    for t in r["out"]:
        assert "語学" in by_title[t]["study_type"], t


def test_each_type_filter_only_returns_confirmed_matches():
    """留学の種別（③）: どの種別でも、並ぶのは種別が確認できたものだけ。"""
    items = _real_items()
    by_title = {i["title"]: i for i in items}
    for t in ("学位取得", "交換留学", "研究", "語学", "インターン"):
        r = run_filter(items, types=[t])
        for title in r["out"]:
            assert t in by_title[title]["study_type"], (t, title)


def test_help_guide_button_and_dialog_exist():
    # 右上の「使い方・注意点」ボタンと、押すと開くガイド（<dialog>）があること
    html = open(os.path.join(os.path.dirname(__file__), "..", "public", "index.html"), encoding="utf-8").read()
    assert 'id="helpBtn"' in html and "使い方・注意点" in html
    assert '<dialog class="guide" id="guideDlg"' in html
    # 最重要の注意（公式ページで確認）と「要確認」の説明が入っている
    assert "公式ページを見る" in html and "要確認" in html
    assert "showModal" in html
