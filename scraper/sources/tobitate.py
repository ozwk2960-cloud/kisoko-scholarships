"""トビタテ！留学JAPAN 新・日本代表プログラム（大学生等対象）。

トビタテのサイトは JS 描画・画像主体で、募集要項の詳細（金額・締切日）は PDF にある。
そのため HTML からは「いま大学生等向けの募集が開いているか（第何期か）」だけを判定し、
金額・支援内容などの安定情報は config.CURATED_TOBITATE_UV から補う。

判定材料: トップページのニュース見出し（「募集開始しました：…大学生等（第N期）」
「募集終了しました：…大学生等（第N期）」）と、大学生等対象ページ（/newprogram/uv/）の
見出し「第N期 応募・選考スケジュール」。
"""

from __future__ import annotations

import re
from datetime import date
from typing import List, Optional, Tuple

from bs4 import BeautifulSoup

from .. import config
from ..models import Scholarship, make_id
from ..normalize import clean_text, truncate, last_date_in, contains, to_halfwidth
from .base import BaseSource


class TobitateSource(BaseSource):
    name = "トビタテ"
    slug = "tobitate"

    def fetch_items(self) -> List[Scholarship]:
        top_html = self.fetch(config.TOBITATE_TOP_URL)
        status, term_from_news, news_date, news_headline = self._read_news_status(top_html)

        uv_html = self.fetch(config.TOBITATE_UV_URL)
        uv_soup = BeautifulSoup(uv_html, "lxml")
        term = self._read_term(uv_soup) or term_from_news

        if status is None and term is None:
            raise RuntimeError(
                "トビタテ: 大学生等対象プログラムの募集状況を判定できませんでした（サイト構造変更の可能性）"
            )

        curated = config.CURATED_TOBITATE_UV
        term_label = f"・第{term}期" if term else ""
        title = f"トビタテ！留学JAPAN 新・日本代表プログラム（大学生等対象{term_label}）"

        is_open = status == "open"
        is_closed = status == "closed"

        if is_open:
            deadline_type = "annual"
            period_text = (
                "現在募集中。応募は在籍大学の学内選考を経て行うため、"
                "学内締切は所属大学の国際交流担当に確認。募集要項で最新日程を確認すること。"
            )
        elif is_closed:
            deadline_type = "unknown"
            period_text = (
                f"直近の募集（{news_headline or '大学生等対象'}）は終了。"
                "次期の募集時期は公式サイト・募集要項で確認。"
            )
        else:
            deadline_type = "annual"
            period_text = "募集時期は年度により変動。公式サイト・募集要項で最新日程を確認。"

        tags = list(curated["tags"])
        if is_closed:
            tags.append("現在は募集していません")
        elif is_open:
            tags.append("募集中")

        # 説明文はキュレーション固定（サイトの meta は募集状況の記述がずれることがあるため）
        desc = truncate(curated["description"], 200)

        item = Scholarship(
            id=make_id(self.slug, "shin-nihon-daihyo", "uv"),
            source=self.name,
            source_url=config.TOBITATE_UV_URL,
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
            duration_text=curated["duration_text"],
            deadline=None,  # HTML から確実な締切日は取れない
            deadline_type=deadline_type,
            application_period_text=truncate(period_text, 300),
            description=desc,
            tags=tags,
        )
        return [item]

    # -- ニュース見出しから募集状況 --
    def _read_news_status(
        self, html: str
    ) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
        """(status, term, date_iso, headline) を返す。status は 'open'|'closed'|None。"""
        soup = BeautifulSoup(html, "lxml")
        candidates: List[Tuple[str, str, str, str]] = []  # (date_iso, status, term, headline)

        for a in soup.find_all("a", href=True):
            # シグナルはアンカー自身のテキストから取る（親ブロックだと隣の記事が混ざる）
            text = clean_text(a.get_text(" ", strip=True))
            if not contains(config.TOBITATE_PROGRAM_RE, text):
                continue
            if not contains(config.TOBITATE_UNIV_RE, text):
                continue

            # 末尾に連結された日付・カテゴリラベルを落とす
            headline = re.split(r"\s+\d{4}年\d{1,2}月\d{1,2}日", text)[0][:100]

            if contains(config.TOBITATE_CLOSED_RE, headline):
                st = "closed"
            elif contains(config.TOBITATE_OPEN_RE, headline):
                st = "open"
            else:
                continue

            d = last_date_in(text) or "0000-00-00"
            m = re.search(config.TOBITATE_UNIV_TERM_RE, to_halfwidth(text))
            term = m.group(1) if m else None
            candidates.append((d, st, term, headline))

        if not candidates:
            return None, None, None, None

        candidates.sort(key=lambda t: t[0], reverse=True)
        d, st, term, headline = candidates[0]
        return st, term, (None if d == "0000-00-00" else d), headline

    def _read_term(self, soup: BeautifulSoup) -> Optional[str]:
        for h in soup.find_all(["h1", "h2", "h3"]):
            m = re.search(config.TOBITATE_TERM_RE, to_halfwidth(h.get_text(" ", strip=True)))
            if m:
                return m.group(1)
        return None
