"""JASSO 海外留学支援制度（学部学位取得型／大学院学位取得型）。

構造:
  index ページ  -> 年度別ページ（.../<key>/YYYY.html）へのリンク一覧
  年度別ページ  -> h1（制度名）, 「応募受付・審査実施日程」表, 「※募集終了」表記

金額・対象学年などページに載らない安定情報は config.CURATED_JASSO から補う。
"""

from __future__ import annotations

import re
from typing import List, Optional

from bs4 import BeautifulSoup

from .. import config
from ..models import Scholarship, make_id
from ..normalize import clean_text, truncate, last_date_in, contains
from .base import BaseSource

_YEAR_LINK_RE = re.compile(r"/scholarship_a/([a-z]+)/(\d{4})\.html")


class JassoSource(BaseSource):
    name = "JASSO"
    slug = "jasso"

    def fetch_items(self) -> List[Scholarship]:
        items: List[Scholarship] = []
        for prog in config.JASSO_PROGRAMS:
            if not prog.get("enabled"):
                continue
            items.extend(self._fetch_program(prog))
        if not items:
            raise RuntimeError("JASSO: 1件も抽出できませんでした（サイト構造変更の可能性）")
        return items

    # -- プログラム単位 --
    def _fetch_program(self, prog: dict) -> List[Scholarship]:
        html = self.fetch(prog["index_url"])
        soup = BeautifulSoup(html, "lxml")
        main = soup.find("main") or soup

        years: List[tuple] = []  # (year:int, url:str)
        for a in main.find_all("a", href=True):
            m = _YEAR_LINK_RE.search(a["href"])
            if not m or m.group(1) != prog["key"]:
                continue
            url = a["href"]
            if url.startswith("/"):
                url = config.JASSO_BASE + url
            years.append((int(m.group(2)), url))

        years = sorted(set(years), key=lambda t: t[0], reverse=True)
        years = years[: config.JASSO_YEARS_TO_FETCH]

        out: List[Scholarship] = []
        for year, url in years:
            try:
                item = self._parse_year_page(prog, year, url)
            except Exception as e:  # 1年度分の失敗は他をブロックしない
                raise RuntimeError(f"JASSO {prog['key']} {year}: {e}") from e
            if item is not None:
                out.append(item)
        return out

    # -- 年度ページ --
    def _parse_year_page(self, prog: dict, year: int, url: str) -> Optional[Scholarship]:
        html = self.fetch(url)
        soup = BeautifulSoup(html, "lxml")

        h1 = soup.find("h1")
        h1_text = clean_text(h1.get_text(" ", strip=True), fold=False) if h1 else ""

        deadline, period_text = self._extract_schedule(soup)

        # 未公開のプレースホルダーページ（h1 が空・日程表なし）はスキップ
        if not h1_text and not period_text:
            return None

        title = h1_text or f"{year}年度海外留学支援制度（{prog['label']}）"
        page_text = soup.get_text(" ", strip=True)
        closed = contains(config.JASSO_CLOSED_RE, page_text)

        # description: h1 直後の最初の段落
        desc = None
        if h1:
            p = h1.find_next("p")
            if p:
                desc = truncate(p.get_text(" ", strip=True), 200)

        curated = config.CURATED_JASSO[prog["key"]]

        if deadline:
            deadline_type = "fixed"
        elif closed:
            deadline_type = "unknown"
        else:
            deadline_type = "annual"

        tags = list(curated["tags"])
        if closed:
            tags.append("現在は募集していません")

        return Scholarship(
            id=make_id(self.slug, prog["key"], str(year)),
            source=self.name,
            source_url=url,
            title=title,
            provider=curated["provider"],
            category="public",
            amount_text=curated["amount_text"],
            amount_monthly_jpy=curated["amount_monthly_jpy"],
            target_degree=list(curated["target_degree"]),
            target_fields=list(curated["target_fields"]),
            eligible_universities=list(curated["eligible_universities"]),
            requires_university_nomination=curated["requires_university_nomination"],
            destination_countries=["全世界"],
            study_type=list(curated["study_type"]),
            duration_text="1年以上",
            deadline=deadline,  # 募集終了後も参考として日付は残す（フロントは既定で過去を非表示）
            deadline_type=deadline_type,
            application_period_text=period_text,
            description=desc,
            tags=tags,
        )

    def _extract_schedule(self, soup: BeautifulSoup):
        """(deadline_iso or None, period_text or None) を返す。"""
        # 「応募受付・審査実施日程」見出しの直後のテーブルを探す
        heading = None
        for h in soup.find_all(["h2", "h3"]):
            if contains(config.JASSO_SCHEDULE_HEADING_RE, h.get_text(" ", strip=True)):
                heading = h
                break
        if heading is None:
            return None, None

        table = heading.find_next("table")
        if table is None:
            return None, None

        deadline: Optional[str] = None
        period_bits: List[str] = []
        for tr in table.find_all("tr"):
            cells = [clean_text(c.get_text(" ", strip=True)) for c in tr.find_all(["th", "td"])]
            row = " ".join(cells)
            if not row:
                continue
            if contains(config.JASSO_DEADLINE_ROW_RE, row):
                d = last_date_in(row)
                if d and (deadline is None or d > deadline):
                    deadline = d
                period_bits.append(row)
        period_text = truncate(" / ".join(period_bits), 300) if period_bits else None
        return deadline, period_text
