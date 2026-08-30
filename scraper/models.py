"""Scholarship データモデルと JSON 変換。

出力フィールドは scraper/schema.json と一致させること。
解析できなかった任意項目は None のまま出す（欠損とハルシネーションを区別するため）。
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import List, Optional

VALID_DEGREES = {"bachelor", "master", "doctor", "research"}
VALID_CATEGORIES = {"public", "university", "private"}
VALID_DEADLINE_TYPES = {"fixed", "rolling", "annual", "unknown"}


@dataclass
class Scholarship:
    # --- 必須 ---
    id: str
    source: str
    source_url: str
    title: str
    provider: str
    category: str                       # public | university | private

    # --- 任意（不明なら None / 空リスト）---
    amount_text: Optional[str] = None
    amount_monthly_jpy: Optional[int] = None
    target_degree: List[str] = field(default_factory=list)
    target_fields: List[str] = field(default_factory=list)
    eligible_universities: List[str] = field(default_factory=list)
    requires_university_nomination: Optional[bool] = None
    destination_countries: List[str] = field(default_factory=list)
    study_type: List[str] = field(default_factory=list)
    duration_text: Optional[str] = None
    deadline: Optional[str] = None       # ISO date or None
    deadline_type: str = "unknown"       # fixed | rolling | annual | unknown
    application_period_text: Optional[str] = None
    description: Optional[str] = None
    tags: List[str] = field(default_factory=list)

    # --- 収集メタ（merge で設定）---
    last_seen: Optional[str] = None      # ISO date
    first_seen: Optional[str] = None     # ISO date

    def validate_light(self) -> None:
        """スキーマ検証の前に呼ぶ軽い自己チェック。"""
        for f_ in ("id", "source", "source_url", "title", "provider", "category"):
            if not getattr(self, f_):
                raise ValueError(f"{self.id or '<no id>'}: 必須フィールド '{f_}' が空です")
        if self.category not in VALID_CATEGORIES:
            raise ValueError(f"{self.id}: category が不正: {self.category!r}")
        if self.deadline_type not in VALID_DEADLINE_TYPES:
            raise ValueError(f"{self.id}: deadline_type が不正: {self.deadline_type!r}")
        bad = set(self.target_degree) - VALID_DEGREES
        if bad:
            raise ValueError(f"{self.id}: target_degree に不正値: {bad}")

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


def make_id(source_slug: str, *parts: str) -> str:
    """安定 ID を生成。例: make_id('jasso', 'daigakuin', '2026') -> 'jasso-daigakuin-2026'"""
    chunks = [source_slug] + [str(p).strip().lower().replace(" ", "-") for p in parts if p]
    return "-".join(chunks)
