"""大阪大学 留学助成制度（学内アグリゲートページ）。

このページ自体が「大学を通じて応募する奨学金（＝学内推薦が必要）」と
「個人で直接応募する奨学金」の一覧表になっている。各行を1件として取り込み、
学内推薦の有無をセクションから決定する。

- KOAN 掲示日が古い行（過年度の募集）は除外。
- JASSO・トビタテなど本ツールが直接スクレイプ済みの制度は除外（重複回避）。
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
from ..normalize import clean_text, truncate, parse_jp_date, contains
from .base import BaseSource

_DATE_CELL_RE = re.compile(r"20\d{2}\s*[/／]\s*\d{1,2}\s*[/／]\s*\d{1,2}")


class OsakaUSource(BaseSource):
    name = "大阪大学"
    slug = "osaka"

    def fetch_items(self) -> List[Scholarship]:
        soup = BeautifulSoup(self.fetch(config.OSAKA_SCHOLARSHIP_URL), "lxml")
        main = soup.find("main") or soup.body or soup
        tables = main.find_all("table")
        if len(tables) < 2:
            raise RuntimeError("阪大: 想定した2つの一覧表が見つかりません（ページ構造変更の可能性）")

        cutoff = (date.today() - timedelta(days=config.OSAKA_MAX_AGE_DAYS)).isoformat()
        items: List[Scholarship] = []
        # table[0] = 大学を通じて応募（学内推薦あり）, table[1] = 個人で直接応募
        items += self._parse_table(tables[0], requires_nomination=True, cutoff=cutoff)
        items += self._parse_table(tables[1], requires_nomination=False, cutoff=cutoff)

        if not items:
            raise RuntimeError("阪大: 有効な行を1件も抽出できませんでした")
        return items

    def _parse_table(self, table, *, requires_nomination: bool, cutoff: str) -> List[Scholarship]:
        out: List[Scholarship] = []
        seen: set = set()
        cur: Optional[dict] = None

        def flush():
            if not (cur and cur["posted"] and cur["posted"] >= cutoff):
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
                if not title or contains(config.OSAKA_EXCLUDE_TITLE_RE, title):
                    cur = None
                    continue
                cur = {
                    "posted": parse_jp_date(first.replace("／", "/")),
                    "title": title,
                    "url": self._pick_url(name_cell),
                    "target": None,
                    "amount": None,
                }
            elif len(tds) == 1 and cur is not None:
                line = clean_text(tds[0].get_text(" ", strip=True), fold=False)
                if line.startswith("【対象】"):
                    cur["target"] = line[len("【対象】"):].strip()
                elif line.startswith("【内容】"):
                    cur["amount"] = line[len("【内容】"):].strip()
                # 【応募書類】等は無視

        flush()
        return out

    def _pick_url(self, cell) -> str:
        a = cell.find("a", href=True)
        if not a:
            return config.OSAKA_SCHOLARSHIP_URL
        href = urljoin(config.OSAKA_SCHOLARSHIP_URL, a["href"])
        host = urlparse(href).netloc
        if re.search(config.OSAKA_INTERNAL_HOST_RE, host):
            return config.OSAKA_SCHOLARSHIP_URL
        return href

    def _build(self, cur: dict, requires_nomination: bool) -> Scholarship:
        title = cur["title"]
        category = "public" if contains(r"政府|県|府|JASSO|日本学生支援機構", title) else "private"
        if contains(r"大阪大学|未来基金|阪大", title):
            category = "university"

        study_type: List[str] = []
        if contains(r"語学", title):
            study_type.append("語学")
        if contains(r"交換留学", title):
            study_type.append("交換留学")

        desc_bits = []
        if cur["target"]:
            desc_bits.append("対象: " + cur["target"])
        if cur["amount"]:
            desc_bits.append("内容: " + cur["amount"])
        description = truncate(" / ".join(desc_bits), 200) if desc_bits else None

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
            target_degree=[],
            target_fields=["全分野"],
            eligible_universities=["大阪大学"],
            requires_university_nomination=requires_nomination,
            destination_countries=["全世界"],
            study_type=study_type,
            duration_text=None,
            deadline=None,
            deadline_type="unknown",
            application_period_text=truncate(period, 260),
            description=description,
            tags=["大阪大学掲載"] + (["学内選考あり"] if requires_nomination else ["直接応募"]),
        )


def _slug_hash(title: str) -> str:
    import hashlib

    return hashlib.sha1(title.encode("utf-8")).hexdigest()[:10]
