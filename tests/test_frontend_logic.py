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
    # 日付の書式（fmtDate など）は MATCH-LOGIC 区間からも使う
    dates = re.search(r"function parseDate\(.*?\n(?=/\* =+ マッチ判定)", html, re.S)
    assert dates, "日付ユーティリティが見つかりません"
    return "\n".join(consts) + "\n" + dates.group(0) + "\n" + region.group(0)


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


# ---- 並び替え（2026-11-11）: どの並びでも締切切れ・募集終了は出さない／出すときは末尾 ----

def run_sort(items, sort, today="2026-11-11", **cond):
    """絞り込み後に compareFor(sort) で並べたタイトル一覧を返す（score は与えた値を使う）。"""
    state = {"degree": None, "field": None, "region": "", "types": [], "nomination": "any",
             "osakaOnly": False, "hidePast": True, "soonOnly": False, "showUnverified": True, "query": ""}
    state.update(cond)
    script = _js_prelude() + """
const input = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const state = Object.assign({}, input.state, { types: new Set(input.state.types) });
function daysLeftOf(it) {
  if (!it.deadline) return null;
  return Math.round((new Date(it.deadline + "T00:00:00") - new Date(input.today + "T00:00:00")) / 86400000);
}
const entries = input.items.map(it => ({ item: it, sc: { score: it._score || 0, daysLeft: daysLeftOf(it) } }))
  .filter(e => passesHardFilters(e.item, e.sc.daysLeft));
entries.sort(compareFor(input.sort));
console.log(JSON.stringify(entries.map(e => e.item.title)));
"""
    p = subprocess.run(["node", "-e", script],
                       input=json.dumps({"items": items, "state": state, "today": today, "sort": sort}),
                       capture_output=True, text=True, check=True)
    return json.loads(p.stdout)


SORT_ITEMS = [
    item("締切12/1", deadline="2026-12-01", _score=10),
    item("締切11/20", deadline="2026-11-20", _score=5),
    item("学内募集中", application_status="open", koan={"posted": "2026-11-09"}, koan_posted="2026-11-09", _score=50),
    item("締切未定", _score=40, koan_posted="2026-10-01"),
    item("締切切れ", deadline="2026-10-01", _score=99, koan_posted="2026-11-10"),
    item("募集終了", application_status="closed", _score=99, koan_posted="2026-11-10"),
]


def test_sort_by_deadline_hides_past_and_orders_known_dates_first():
    assert run_sort(SORT_ITEMS, "deadline") == ["締切11/20", "締切12/1", "学内募集中", "締切未定"]


def test_sort_by_koan_newest_first_without_past():
    out = run_sort(SORT_ITEMS, "koan")
    assert out == ["学内募集中", "締切未定", "締切12/1", "締切11/20"]   # 掲示なしはスコア順で後ろ


def test_sort_by_score_default():
    assert run_sort(SORT_ITEMS, "score") == ["学内募集中", "締切未定", "締切12/1", "締切11/20"]


def test_past_items_go_last_in_every_sort_when_shown():
    for key in ("score", "deadline", "koan"):
        out = run_sort(SORT_ITEMS, key, hidePast=False)
        assert set(out[-2:]) == {"締切切れ", "募集終了"}, (key, out)


def run_reasons(items, sort, today="2026-11-11"):
    """並び替え sort での「この順位の理由」の文面を {タイトル: 文面} で返す。"""
    script = _js_prelude() + """
const input = JSON.parse(require('fs').readFileSync(0, 'utf8'));
function daysLeftOf(it) {
  if (!it.deadline) return null;
  return Math.round((new Date(it.deadline + "T00:00:00") - new Date(input.today + "T00:00:00")) / 86400000);
}
const out = Object.fromEntries(input.items.map(it => [it.title,
  sortReason({ item: it, sc: { score: it._score || 0, reasons: it._reasons || [], daysLeft: daysLeftOf(it) } }, input.sort)]));
console.log(JSON.stringify(out));
"""
    p = subprocess.run(["node", "-e", script],
                       input=json.dumps({"items": items, "today": today, "sort": sort}),
                       capture_output=True, text=True, check=True)
    return json.loads(p.stdout)


def test_reason_for_score_sort_is_unchanged():
    items = [item("A", _score=35.4, _reasons=["阪大対象", "締切2日"]), item("B", _score=3)]
    r = run_reasons(items, "score")
    assert r["A"] == "阪大対象 ／ 締切2日（スコア 35）"
    assert r["B"] == "現在の条件では加点なし（スコア 3）"


def test_reason_follows_deadline_sort():
    r = run_reasons(SORT_ITEMS, "deadline")
    assert r["締切11/20"].startswith("締切が近い順: 締切まで9日（2026/11/20）")
    assert "学内募集中" in r["学内募集中"] and "締切日のある制度の後" in r["学内募集中"]
    assert r["締切未定"].startswith("締切が近い順: 締切未定のため後ろ")
    assert r["締切切れ"].startswith("募集終了・締切切れのため一覧の最後")
    assert r["募集終了"].startswith("募集終了・締切切れのため一覧の最後")
    assert all("マッチ度順（スコア" in v for v in r.values())


def test_reason_follows_koan_sort():
    r = run_reasons(SORT_ITEMS, "koan")
    assert r["学内募集中"].startswith("KOAN掲示が新しい順: 掲示日 2026/11/09")
    assert r["締切未定"].startswith("KOAN掲示が新しい順: 掲示日 2026/10/01")   # koan_posted だけの行
    assert r["締切12/1"].startswith("KOAN掲示が新しい順: KOAN掲示が無いため後ろ")
    assert "スコア" not in r["締切12/1"].split("／")[0]


def test_reason_says_closed_items_are_last_in_score_sort_too():
    r = run_reasons(SORT_ITEMS, "score")
    assert r["募集終了"].startswith("募集終了・締切切れのため一覧の最後 ／ ")
    assert r["締切切れ"].startswith("募集終了・締切切れのため一覧の最後 ／ ")
    assert not r["締切12/1"].startswith("募集終了")


def run_params(search):
    """URL クエリ search を paramsToState に通した後の state を返す（DOM はスタブ）。"""
    html = open(INDEX, encoding="utf-8").read()
    fn = re.search(r"function paramsToState\(search\) \{.*?\n\}", html, re.S)
    labels = re.search(r"const DEGREE_LABEL = \{.*?\};", html)
    types = re.findall(r'<input type="checkbox" value="([^"]+)">', html.split('id="fType"')[1].split("</div>")[0])
    assert fn and labels and types
    script = _js_prelude() + labels.group(0) + fn.group(0) + """
const input = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const document = { querySelectorAll: () => input.types.map(v => ({ value: v })) };
const state = { degree: null, field: null, region: "", types: new Set(), nomination: "any", sort: "score", query: "" };
paramsToState(input.search);
console.log(JSON.stringify(Object.assign({}, state, { types: [...state.types] })));
"""
    p = subprocess.run(["node", "-e", script], input=json.dumps({"search": search, "types": types}),
                       capture_output=True, text=True, check=True)
    return json.loads(p.stdout)


def test_url_params_accept_known_values():
    st = run_params("?d=master&f=情報&r=欧州&t=研究,語学&nom=none&sort=koan&q=abc")
    assert (st["degree"], st["field"], st["region"]) == ("master", "情報", "欧州")
    assert st["types"] == ["研究", "語学"]
    assert (st["nomination"], st["sort"], st["query"]) == ("none", "koan", "abc")


def test_url_params_ignore_unknown_and_inherited_names():
    # "constructor" などは Object の継承プロパティ名。通すと絞り込みで例外になり、画面が出なくなる
    for name in ("constructor", "toString", "__proto__", "hasOwnProperty", "x"):
        st = run_params(f"?d={name}&f={name}&r={name}&t={name},語学&nom={name}&sort={name}")
        assert (st["degree"], st["field"], st["region"]) == (None, None, ""), name
        assert st["types"] == ["語学"], name
        assert (st["nomination"], st["sort"]) == ("any", "score"), name


def test_free_word_search_hits_koan_target():
    it = item("財団A", koan={"title": "財団A", "posted": "2026-11-01", "closed": False,
                           "target": "大学間交換留学をする学部生", "content": "月額7万円", "list_url": "https://x"})
    assert run_filter([it], query="交換留学をする")["out"] == ["財団A"]


def test_sort_menu_and_koan_box_in_html():
    html = open(INDEX, encoding="utf-8").read()
    assert 'id="fSort"' in html
    for v in ("score", "deadline", "koan"):
        assert f'<option value="{v}"' in html
    assert "阪大KOAN掲示" in html and "阪大の留学助成ページで見る" in html
    # ガイドにも並び替えの説明がある（UI文言を変えたらガイドも直す）
    assert "締切が近い順" in html.split('id="guideDlg"')[1].split("</dialog>")[0]


def test_nomination_must_shows_koan_rows_on_real_data():
    """学内推薦があるものだけ: 阪大の行はすべて KOAN 掲示の情報（koan）を持つ。"""
    items = _real_items()
    r = run_filter(items, nomination="must", hidePast=False, showUnverified=True)
    by_title = {i["title"]: i for i in items}
    osaka = [t for t in r["out"] if by_title[t]["source"] == "大阪大学"]
    assert osaka
    for t in osaka:
        assert by_title[t].get("koan"), t


def test_safe_url_allows_only_http_https():
    html = open(INDEX, encoding="utf-8").read()
    fn = re.search(r"function safeUrl\(u\) \{.*?\n\}", html, re.S).group(0)
    cases = ["https://a.jp/x", "http://a.jp", " HTTPS://a.jp ", "javascript:alert(1)", " javascript:x",
             "data:text/html,x", "", None, "//evil.example"]
    script = fn + "\nconsole.log(JSON.stringify(%s.map(safeUrl)));" % json.dumps(cases)
    out = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)
    assert out == ["https://a.jp/x", "http://a.jp", "HTTPS://a.jp", "#", "#", "#", "#", "#", "#"]
    # カードのリンクはすべて safeUrl を通す
    assert 'href="${esc(item.source_url)}"' not in html and 'href="${esc(k.list_url)}"' not in html


def test_csp_header_is_set():
    headers = open(os.path.join(ROOT, "public", "_headers"), encoding="utf-8").read()
    assert "Content-Security-Policy:" in headers
    for d in ("default-src 'self'", "frame-ancestors 'none'", "object-src 'none'", "base-uri 'none'"):
        assert d in headers
