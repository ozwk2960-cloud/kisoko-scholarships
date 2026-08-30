"""吉田育英会 日本人派遣留学プログラム。

募集要項は PDF。HTML ページからは「20XX度採用分の募集を行います」等の
募集状況と対象年度だけを取得し、支援内容などは config.CURATED_YOSHIDA から補う。
"""

from __future__ import annotations

import re
from typing import List

from bs4 import BeautifulSoup

from .. import config
from ..models import Scholarship, make_id
from ..normalize import clean_text, contains, to_halfwidth
from .base import BaseSource


class YoshidaSource(BaseSource):
    name = "吉田育英会"
    slug = "yoshida"

    def fetch_items(self) -> List[Scholarship]:
        soup = BeautifulSoup(self.fetch(config.YOSHIDA_GUIDELINE_URL), "lxml")
        main = soup.find("main") or soup.body or soup
        text = clean_text(main.get_text(" ", strip=True))

        closed = contains(config.YOSHIDA_CLOSED_RE, text)
        m = re.search(config.YOSHIDA_OPEN_RE, to_halfwidth(text))
        year = m.group(1) if m else None

        if not closed and year is None:
            raise RuntimeError("吉田育英会: 募集状況を判定できませんでした（ページ構造変更の可能性）")

        c = config.CURATED_YOSHIDA
        year_label = f"{year}年度採用" if year else ""
        title = f"吉田育英会 日本人派遣留学プログラム（{year_label}）".replace("（）", "")

        if closed or year is None:
            deadline_type = "unknown" if closed else "annual"
            period = "現在は募集していません。次年度の募集要項公開を待つこと。" if closed \
                else "募集時期は年度により変動。募集要項PDFで最新日程を確認。"
        else:
            deadline_type = "annual"
            period = (f"{year}年度採用分の募集中。締切は募集要項PDFに記載"
                      "（例年 秋〜冬。推薦依頼校在籍者は大学の学内締切に従う）。")

        tags = list(c["tags"])
        if closed:
            tags.append("現在は募集していません")

        return [Scholarship(
            id=make_id(self.slug, "haken-ryugaku"),
            source=self.name,
            source_url=config.YOSHIDA_GUIDELINE_URL,
            title=title,
            provider=c["provider"],
            category="private",
            amount_text=c["amount_text"],
            amount_monthly_jpy=c["amount_monthly_jpy"],
            target_degree=list(c["target_degree"]),
            target_fields=list(c["target_fields"]),
            eligible_universities=list(c["eligible_universities"]),
            requires_university_nomination=c["requires_university_nomination"],
            destination_countries=["全世界"],
            study_type=list(c["study_type"]),
            duration_text=c["duration_text"],
            deadline=None,
            deadline_type=deadline_type,
            application_period_text=period,
            description=c["description"],
            tags=tags,
        )]
