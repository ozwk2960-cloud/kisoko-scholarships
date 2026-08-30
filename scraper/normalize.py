"""表記ゆれを吸収するユーティリティ。

日付・金額の抽出は「取れなければ None」を返す。推測で埋めない。
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from typing import List, Optional

# 全角数字などを半角へ
def to_halfwidth(s: str) -> str:
    return unicodedata.normalize("NFKC", s or "")


def clean_text(s: Optional[str], fold: bool = True) -> str:
    """連続する空白・改行を1つのスペースにまとめて trim。

    fold=True: NFKC 正規化（全角記号→半角など。日付・金額の解析用）
    fold=False: 文字はそのまま（見出し・タイトルの表示用）
    """
    if not s:
        return ""
    if fold:
        s = to_halfwidth(s)
    s = s.replace("　", " ")
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def truncate(s: str, limit: int = 200) -> str:
    s = clean_text(s)
    if len(s) <= limit:
        return s
    return s[: limit - 1].rstrip() + "…"


# ---- 日付 -------------------------------------------------------------------

_JP_DATE_RE = re.compile(r"(\d{4})\s*[年/．\.]\s*(\d{1,2})\s*[月/．\.]\s*(\d{1,2})")
_ISO_DATE_RE = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})")


def parse_jp_date(text: Optional[str]) -> Optional[str]:
    """文字列から最初の和暦なし日付を ISO(YYYY-MM-DD) で返す。無ければ None。

    例: "2025年10月9日（木曜日）13時" -> "2025-10-09"
    """
    if not text:
        return None
    t = to_halfwidth(text)
    m = _JP_DATE_RE.search(t) or _ISO_DATE_RE.search(t)
    if not m:
        return None
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return date(y, mo, d).isoformat()
    except ValueError:
        return None


def parse_all_jp_dates(text: Optional[str]) -> List[str]:
    """文字列中のすべての日付を出現順に ISO で返す。"""
    if not text:
        return []
    t = to_halfwidth(text)
    out: List[str] = []
    for m in _JP_DATE_RE.finditer(t):
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            out.append(date(y, mo, d).isoformat())
        except ValueError:
            continue
    return out


def last_date_in(text: Optional[str]) -> Optional[str]:
    """締切表現向け: 文字列中で最も遅い日付を返す。"""
    dates = parse_all_jp_dates(text)
    return max(dates) if dates else None


# ---- 金額 -------------------------------------------------------------------

_MAN_RE = re.compile(r"(\d+)\s*万\s*([\d,]{1,7})?")
_NUM_TOKEN_RE = re.compile(r"\d{1,3}(?:,\d{3})+|\d{4,}")


def normalize_amount(text: Optional[str]) -> Optional[int]:
    """月額表現から円単位の整数（複数あれば最小値）を返す。取れなければ None。

    例: "月額177,000円～388,000円"     -> 177000
        "17万7,000円"                 -> 177000
        "月額 60,000〜160,000円"       -> 60000   （範囲の下限）
    金額らしくない小さな数字（10,000未満）や、円の記述が無い文字列は無視する。
    """
    if not text:
        return None
    t = to_halfwidth(text)
    values: List[int] = []

    for m in _MAN_RE.finditer(t):
        man = int(m.group(1))
        rest_s = (m.group(2) or "").replace(",", "")
        rest = int(rest_s) if rest_s else 0
        values.append(man * 10000 + rest)

    if "円" in t:
        for tok in _NUM_TOKEN_RE.findall(t):
            try:
                values.append(int(tok.replace(",", "")))
            except ValueError:
                continue

    values = [v for v in values if v >= 10000]
    return min(values) if values else None


# ---- その他 ---------------------------------------------------------------

def contains(pattern: str, text: Optional[str]) -> bool:
    if not text:
        return False
    return re.search(pattern, to_halfwidth(text)) is not None


def slugify_ascii(s: str) -> str:
    """ID 生成用。英数字とハイフンのみ残す。日本語は落ちるので呼び出し側で年度等を付与する。"""
    s = to_halfwidth(s).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")
