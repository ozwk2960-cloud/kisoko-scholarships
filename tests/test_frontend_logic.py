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


def run_filter(items, **cond):
    """条件 cond（state の上書き）で絞り込み、残ったタイトル一覧を返す。"""
    state = {"degree": None, "field": None, "region": "", "types": [], "nomination": "any",
             "osakaOnly": False, "hidePast": False, "soonOnly": False, "strict": False, "query": ""}
    state.update(cond)
    script = _js_prelude() + """
const input = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const state = Object.assign({}, input.state, { types: new Set(input.state.types) });
const out = input.items.filter(it => passesHardFilters(it, null)).map(it => it.title);
const unv = Object.fromEntries(input.items.map(it => [it.title, unverifiedConditions(it)]));
console.log(JSON.stringify({ out, unv }));
"""
    p = subprocess.run(["node", "-e", script], input=json.dumps({"items": items, "state": state}),
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


def test_unknown_is_kept_but_flagged_in_normal_mode():
    r = run_filter([UNKNOWN], degree="bachelor")
    assert r["out"] == ["未確認"]
    assert r["unv"]["未確認"] == ["学年・課程"]


def test_strict_mode_drops_unknown():
    r = run_filter([UG_EXCHANGE, UNKNOWN], degree="bachelor", strict=True)
    assert r["out"] == ["学部交換"]


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


def test_user_scenario_on_real_data():
    """利用者が実際に試した検索を、現行の scholarships.json で再現する。"""
    path = os.path.join(ROOT, "public", "scholarships.json")
    if not os.path.exists(path):
        pytest.skip("scholarships.json 未生成")
    items = json.load(open(path, encoding="utf-8"))["scholarships"]
    r = run_filter(items, degree="bachelor", field="システム", types=["交換留学"], nomination="none")
    assert not any("INPEX" in t for t in r["out"])
    by_title = {i["title"]: i for i in items}
    for t in r["out"]:
        it = by_title[t]
        # 残ったものに「学部が対象外と確認済み」の制度は無い
        assert not it["target_degree"] or "bachelor" in it["target_degree"], t
        assert it["requires_university_nomination"] is False, t
