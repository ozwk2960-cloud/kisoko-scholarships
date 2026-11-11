"""大阪大学 留学助成制度（学内アグリゲートページ）。

このページ自体が「大学を通じて応募する奨学金（＝学内推薦が必要）」と
「個人で直接応募する奨学金」の一覧表になっている。各行を1件として取り込み、
学内推薦の有無をセクションから決定する。

- KOAN 掲示日が古い行（過年度の募集）は除外。
- トビタテ・JASSO学位取得型など本ツールが直接スクレイプ済みの制度は阪大の行にしない（重複回避）。
  その行は `self.koan_links` に残し、`attach_koan()` で同じ期・年度の全国カードに添付する。
- 学内ログインが必要なリンクは公開の一覧ページ URL にフォールバック。
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import List, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .. import config
from ..models import Scholarship, make_id
from ..normalize import clean_text, truncate, parse_jp_date, contains, to_halfwidth
from .base import BaseSource, Fetcher

_DATE_CELL_RE = re.compile(r"20\d{2}\s*[/／]\s*\d{1,2}\s*[/／]\s*\d{1,2}")


class OsakaUSource(BaseSource):
    name = "大阪大学"
    slug = "osaka"

    def __init__(self, fetcher: Optional[Fetcher] = None, today: Optional[date] = None) -> None:
        super().__init__(fetcher)
        # 「過年度の行」を判定する基準日。テストでは固定日を渡す（fixture が時限で壊れないように）
        self.today = today
        # 別ソースの全国制度に添付する KOAN 行。取得・解析が最後まで成功したときだけ koan_links_ok=True
        self.koan_links: List[dict] = []
        self.koan_links_ok = False

    def fetch_items(self) -> List[Scholarship]:
        self.koan_links = []
        self.koan_links_ok = False
        soup = BeautifulSoup(self.fetch(config.OSAKA_SCHOLARSHIP_URL), "lxml")
        main = soup.find("main") or soup.body or soup
        tables = main.find_all("table")
        if len(tables) < 2:
            raise RuntimeError("阪大: 想定した2つの一覧表が見つかりません（ページ構造変更の可能性）")

        cutoff = ((self.today or date.today()) - timedelta(days=config.OSAKA_MAX_AGE_DAYS)).isoformat()
        items: List[Scholarship] = []
        # table[0] = 大学を通じて応募（学内推薦あり）, table[1] = 個人で直接応募
        items += self._parse_table(tables[0], requires_nomination=True, cutoff=cutoff)
        items += self._parse_table(tables[1], requires_nomination=False, cutoff=cutoff)

        if not items:
            raise RuntimeError("阪大: 有効な行を1件も抽出できませんでした")
        self.koan_links_ok = True
        return items

    def _parse_table(self, table, *, requires_nomination: bool, cutoff: str) -> List[Scholarship]:
        out: List[Scholarship] = []
        seen: set = set()
        cur: Optional[dict] = None

        def flush():
            if not (cur and cur["posted"] and cur["posted"] >= cutoff):
                return
            if cur["excluded"]:
                # 別ソースで取っている全国制度の行: カードにはせず、添付用に残す
                self.koan_links.append(_koan_info(cur, requires_nomination))
                return
            item = self._build(cur, requires_nomination)
            if item.id in seen:      # 同一表内に同名・同日の行が重複することがある
                return
            seen.add(item.id)
            out.append(item)

        for tr in table.find_all("tr"):
            tds = tr.find_all(["td", "th"])
            if not tds:
                continue
            first = clean_text(tds[0].get_text(" ", strip=True), fold=True)

            if len(tds) >= 2 and _DATE_CELL_RE.search(first):
                flush()
                name_cell = tds[1]
                title = clean_text(name_cell.get_text(" ", strip=True), fold=False)
                if not title:
                    cur = None
                    continue
                cur = {
                    "excluded": bool(contains(config.OSAKA_EXCLUDE_TITLE_RE, title)),
                    "posted": parse_jp_date(first.replace("／", "/")),
                    # 日付セルに「募集終了」と書かれていれば学内の募集は終了している
                    "closed": "募集終了" in first,
                    "note": None,
                    "title": title,
                    "url": self._pick_url(name_cell),
                    "target": None,
                    "amount": None,
                }
            elif len(tds) == 1 and cur is not None:
                line = clean_text(tds[0].get_text(" ", strip=True), fold=False)
                if "【対象】" in line:
                    # 「※本学では…は実施しない予定です。【対象】…」のように前置きが付く行がある
                    pre, _, rest = line.partition("【対象】")
                    cur["target"] = rest.strip()
                    if pre.strip():
                        cur["note"] = pre.strip()
                elif line.startswith("【内容】"):
                    cur["amount"] = line[len("【内容】"):].strip()
                # 【応募書類】等は無視

        flush()
        return out

    def _pick_url(self, cell) -> str:
        a = cell.find("a", href=True)
        if not a:
            return config.OSAKA_SCHOLARSHIP_URL
        href = urljoin(config.OSAKA_SCHOLARSHIP_URL, a["href"].strip())
        parsed = urlparse(href)
        # http/https 以外（javascript: など）はリンクにしない
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return config.OSAKA_SCHOLARSHIP_URL
        if re.search(config.OSAKA_INTERNAL_HOST_RE, parsed.netloc):
            return config.OSAKA_SCHOLARSHIP_URL
        return href

    def _build(self, cur: dict, requires_nomination: bool) -> Scholarship:
        title = cur["title"]
        category = "public" if contains(r"政府|県|府|JASSO|日本学生支援機構", title) else "private"
        if contains(r"大阪大学|未来基金|阪大", title):
            category = "university"

        # 1) 一覧ページの【対象】【タイトル】に「明記されている語」だけを拾う（推測しない）
        facts = parse_target(cur["target"], title)
        # 2) 一覧に【対象】が無い制度は、公式情報で確認済みの補正表で埋める
        note = None
        for rule in config.OSAKA_CURATED:
            if re.search(rule["match"], title):
                for key in ("target_degree", "study_type", "target_fields", "destination_countries"):
                    if key in rule:
                        facts[key] = list(rule[key])
                note = rule.get("note")
                break

        # 3) 募集回ごとの締切・状況（年度入りタイトルか掲示日で特定の回にだけ当てる）
        deadline = None
        status = "closed" if cur["closed"] else ("open" if requires_nomination else None)
        round_note = None
        for r in config.OSAKA_ROUNDS:
            if not re.search(r["match"], title):
                continue
            if "posted" in r and r["posted"] != cur["posted"]:
                continue
            deadline = r.get("deadline") or deadline
            status = r.get("application_status") or status
            round_note = r.get("note")
            break

        # 一覧の【対象】【内容】と行の注記は koan（カードの「阪大KOAN掲示」欄）に入れるので、説明文には重ねない
        desc_bits = []
        if note:
            desc_bits.append(note)
        if round_note:
            desc_bits.append(round_note)
        description = truncate(" / ".join(desc_bits), 420) if desc_bits else None

        nomination_note = (
            "この一覧では『大学を通じて応募する奨学金』に分類（学内選考・学内締切あり）。"
            if requires_nomination else
            "この一覧では『個人で直接応募する奨学金』に分類。"
        )
        period = (
            f"大阪大学 KOAN／マイハンダイ 掲示日 {cur['posted']}。"
            f"{nomination_note} 学内締切・詳細は所属学部／研究科および募集要項で確認。"
        )

        return Scholarship(
            id=make_id(self.slug, _slug_hash(f"{title}|{cur['posted']}")),
            source=self.name,
            source_url=cur["url"],
            title=title,
            provider="大阪大学（留学助成制度一覧に掲載）",
            category=category,
            amount_text=truncate(cur["amount"], 160) if cur["amount"] else None,
            amount_monthly_jpy=None,   # 「月額/総額」「万円」表記が混在するため数値化しない
            target_degree=facts["target_degree"],
            target_fields=facts["target_fields"],
            eligible_universities=["大阪大学"],
            requires_university_nomination=requires_nomination,
            destination_countries=facts["destination_countries"],
            study_type=facts["study_type"],
            duration_text=None,
            deadline=deadline,
            deadline_type="fixed" if deadline else "unknown",
            application_period_text=truncate(period, 260),
            application_status=status,
            koan_posted=cur["posted"],
            koan=_koan_info(cur, requires_nomination),
            description=description,
            tags=["大阪大学掲載"] + (["学内選考あり"] if requires_nomination else ["直接応募"]),
        )


_ALL_DEGREES = ["bachelor", "master", "doctor"]
# 【対象】に明記されたときだけ拾う留学先の語
_DEST_WORDS = ["東南アジア", "南西アジア", "アメリカ", "米国", "中国", "台湾", "韓国", "フランス",
               "スイス", "ドイツ", "イギリス", "英国", "カナダ", "オーストラリア"]


def parse_target(target: Optional[str], title: str) -> dict:
    """【対象】とタイトルから、明記されている条件だけを取り出す。

    読み取れなかった項目は空リストのまま返す（＝「不明」。ツール上は『要確認』になる）。
    「全分野」「全世界」などを既定値として補うことはしない。
    """
    t = target or ""
    out = {"target_degree": [], "target_fields": [], "destination_countries": [], "study_type": []}

    # 学年・課程
    if re.search(r"学部[・、]?(?:専攻|研究科)?(?:は|を)?\s*(?:不問|問いません)|所属学部[・、]研究科不問", t):
        out["target_degree"] = list(_ALL_DEGREES)
    elif re.search(r"本学正規生", t):
        out["target_degree"] = list(_ALL_DEGREES)
    elif re.search(r"博士前期課程", t):
        out["target_degree"] = ["master"]
    elif re.search(r"大学院(?:の)?正規生|本学大学院生|大学院生", t):
        out["target_degree"] = ["master", "doctor"]
    elif re.search(r"学部生", t):
        out["target_degree"] = ["bachelor"]

    # 専攻
    if re.search(r"理工系|理系|自然科学分野", t):
        out["target_fields"] = ["理工系"]
    elif re.search(r"専攻(?:は|を)?\s*(?:不問|問いません)", t):
        out["target_fields"] = ["全分野"]

    # 留学の種別（タイトルか【対象】に書かれている語だけ）
    # 「交換留学は含みません」「交換留学を除く」は否定なので、種別として拾わない
    text = re.sub(r"[（(]?交換留学(?:は|を)(?:含みません|含まない|除く|対象外)[。）)]*", "", title + " " + t)
    if "語学" in text:
        out["study_type"].append("語学")
    if "交換留学" in text:
        out["study_type"].append("交換留学")

    # 留学先
    out["destination_countries"] = [w for w in _DEST_WORDS if w in t]
    return out


def _koan_info(cur: dict, requires_nomination: bool) -> dict:
    """阪大の留学助成ページ（KOAN掲示一覧）の1行に書かれていることだけをまとめる。"""
    return {
        "title": cur["title"],
        "posted": cur["posted"],
        "closed": bool(cur["closed"]),
        "nominated": requires_nomination,
        "target": truncate(cur["target"], 300) if cur["target"] else None,
        "content": truncate(cur["amount"], 300) if cur["amount"] else None,
        "note": cur.get("note"),
        "list_url": config.OSAKA_SCHOLARSHIP_URL,
    }


def _round_key(title: str) -> Optional[tuple]:
    """全国制度の「どの回か」を表すキー。分からなければ None（＝添付しない）。

    - トビタテ: 期（第19期 → ("tobitate", "19")）
    - JASSO 学位取得型: 課程と年度（2027年度…大学院学位取得型 → ("jasso", "大学院", "2027")）
    """
    t = to_halfwidth(title or "")
    if "トビタテ" in t:
        m = re.search(r"第\s*(\d+)\s*期", t)
        return ("tobitate", m.group(1)) if m else None
    m = re.search(r"(大学院|学部)学位取得型", t)
    if m:
        y = re.search(r"(20\d{2})\s*年度", t)
        return ("jasso", m.group(1), y.group(1)) if y else None
    return None


def match_koan(title: str, koan_links: List[dict]) -> Optional[dict]:
    """全国制度のタイトルと同じ期・年度の KOAN 行を返す。期・年度が合わない行は返さない。

    トビタテの「新一年生対象」の行は別の募集なので、大学生等対象のカードには付けない。
    同じ回の行が複数あれば、掲示日の新しいものを返す。
    """
    key = _round_key(title)
    if key is None:
        return None
    cands = [k for k in koan_links
             if _round_key(k["title"]) == key and "新一年生" not in k["title"]]
    if not cands:
        return None
    return max(cands, key=lambda k: k["posted"] or "")


def attach_koan(items: List[Scholarship], koan_links: List[dict]) -> int:
    """全国制度（トビタテ・JASSO）の各件に、同じ回の KOAN 行を添付する。添付した件数を返す。"""
    n = 0
    for it in items:
        k = match_koan(it.title, koan_links)
        if k:
            it.koan = dict(k)
            if not it.koan_posted:
                it.koan_posted = k["posted"]
            n += 1
    return n


def _slug_hash(title: str) -> str:
    import hashlib

    return hashlib.sha1(title.encode("utf-8")).hexdigest()[:10]
