"""船井情報科学振興財団 海外留学奨学金（大学院・博士号取得／学部）。

応募要項ページは <dl><div><dt>ラベル</dt><dd>内容</dd></div></dl> 構造。
「応募期間」から締切、「支援内容」から金額テキストを動的に取得する。
対象学年・分野など安定情報は config.FUNAI_PROGRAMS から補う。
"""

from __future__ import annotations

from typing import Dict, List

from bs4 import BeautifulSoup

from .. import config
from ..models import Scholarship, make_id
from ..normalize import clean_text, truncate, last_date_in
from .base import BaseSource


class FunaiSource(BaseSource):
    name = "船井情報科学振興財団"
    slug = "funai"

    def fetch_items(self) -> List[Scholarship]:
        items = [self._fetch_program(p) for p in config.FUNAI_PROGRAMS]
        if not items:
            raise RuntimeError("船井財団: 1件も抽出できませんでした")
        return items

    def _fetch_program(self, prog: dict) -> Scholarship:
        soup = BeautifulSoup(self.fetch(prog["url"]), "lxml")
        pairs = self._dl_pairs(soup)

        period_text = pairs.get(config.FUNAI_PERIOD_LABEL)
        deadline = last_date_in(period_text) if period_text else None
        amount_text = pairs.get(config.FUNAI_AMOUNT_LABEL)
        # 「支援内容」dd は必要書類まで含むことがあるので金額部分だけ切り出す
        if amount_text:
            amount_text = truncate(amount_text.split("必要書類")[0], 200)
        duration = pairs.get(config.FUNAI_DURATION_LABEL)
        eligibility = pairs.get(config.FUNAI_ELIGIBILITY_LABEL)

        if not (period_text or amount_text or eligibility):
            raise RuntimeError(f"船井財団 {prog['key']}: 応募要項の主要項目が取れませんでした")

        common = config.CURATED_FUNAI_COMMON
        return Scholarship(
            id=make_id(self.slug, prog["key"]),
            source=self.name,
            source_url=prog["url"],
            title=prog["title"],
            provider=common["provider"],
            category="private",
            amount_text=amount_text,
            amount_monthly_jpy=None,   # 米ドル建て・年額のため換算しない
            target_degree=list(prog["target_degree"]),
            target_fields=list(prog["target_fields"]),
            eligible_universities=list(common["eligible_universities"]),
            requires_university_nomination=common["requires_university_nomination"],
            destination_countries=list(common["destination_countries"]),
            study_type=list(common["study_type"]),
            duration_text=truncate(duration, 60) if duration else None,
            deadline=deadline,
            deadline_type="fixed" if deadline else "annual",
            application_period_text=truncate(period_text, 200) if period_text else None,
            description=truncate(eligibility, 200) if eligibility else None,
            tags=list(common["tags"]),
        )

    @staticmethod
    def _dl_pairs(soup: BeautifulSoup) -> Dict[str, str]:
        pairs: Dict[str, str] = {}
        for dt in soup.find_all("dt"):
            dd = dt.find_next_sibling("dd")
            if dd is None:
                continue
            key = clean_text(dt.get_text(" ", strip=True), fold=False)
            pairs.setdefault(key, clean_text(dd.get_text(" ", strip=True)))
        return pairs
