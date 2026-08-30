"""孫正義育英財団。

留学専用の奨学金ではなく、26歳未満の突出した才能を支援する英才育成プログラム
（海外進学・留学時の経済的支援を含む）。募集要項ページから募集状況、top ページの
ニュースから期（第N期）を取得し、支援内容は config.CURATED_MASASON から補う。
"""

from __future__ import annotations

import re
from typing import List, Optional

from bs4 import BeautifulSoup

from .. import config
from ..models import Scholarship, make_id
from ..normalize import clean_text, contains, to_halfwidth
from .base import BaseSource


class MasasonSource(BaseSource):
    name = "孫正義育英財団"
    slug = "masason"

    def fetch_items(self) -> List[Scholarship]:
        req_soup = BeautifulSoup(self.fetch(config.MASASON_REQUIREMENTS_URL), "lxml")
        req_text = clean_text((req_soup.find("main") or req_soup.body or req_soup).get_text(" ", strip=True))
        closed = contains(config.MASASON_CLOSED_RE, req_text)

        term, term_date = self._latest_term(self.fetch(config.MASASON_TOP_URL))

        if not req_text:
            raise RuntimeError("孫正義育英財団: 募集要項ページを読めませんでした")

        c = config.CURATED_MASASON
        term_label = f"第{term}期" if term else ""
        title = f"孫正義育英財団 財団生募集（{term_label}）".replace("（）", "")

        if closed:
            deadline_type = "unknown"
            period = (f"直近（{term_label or '前期'}）の募集は終了。"
                      "例年1〜2月頃に翌期の募集を開始。募集要項で最新情報を確認。")
        else:
            deadline_type = "annual"
            period = (f"{term_label}募集中。応募期間は募集要項を確認"
                      "（例年1〜2月）。")

        tags = list(c["tags"])
        tags.append("現在は募集していません" if closed else "募集中")

        return [Scholarship(
            id=make_id(self.slug, "zaidansei"),
            source=self.name,
            source_url=config.MASASON_REQUIREMENTS_URL,
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

    def _latest_term(self, top_html: str):
        soup = BeautifulSoup(top_html, "lxml")
        best: Optional[tuple] = None  # (date_iso, term)
        for a in soup.find_all("a", href=True):
            text = to_halfwidth(a.get_text(" ", strip=True))
            m = re.search(config.MASASON_TERM_NEWS_RE, text)
            if not m:
                continue
            dm = re.search(r"/(\d{4})/(\d{2})/(\d{2})/", a["href"])
            date_iso = "-".join(dm.groups()) if dm else "0000-00-00"
            cand = (date_iso, m.group(1))
            if best is None or cand[0] > best[0]:
                best = cand
        if best is None:
            return None, None
        return best[1], (None if best[0] == "0000-00-00" else best[0])
