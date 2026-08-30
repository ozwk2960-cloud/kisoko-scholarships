from __future__ import annotations

import pytest

from scraper.normalize import (
    clean_text,
    truncate,
    parse_jp_date,
    parse_all_jp_dates,
    last_date_in,
    normalize_amount,
)


@pytest.mark.parametrize("raw,expected", [
    ("2025年10月9日（木曜日）13時（日本時間）締切", "2025-10-09"),
    ("2026年9月1日(火曜日)～2026年10月1日(木曜日)", "2026-09-01"),   # 最初の日付
    ("2027-01-05 通知", "2027-01-05"),
    ("2026年13月40日", None),        # 不正な日付
    ("日程未定", None),
    ("", None),
])
def test_parse_jp_date(raw, expected):
    assert parse_jp_date(raw) == expected


def test_last_date_in_returns_latest():
    text = "2026年9月1日～2026年10月1日締切 ※2026年10月1日必着"
    assert last_date_in(text) == "2026-10-01"


def test_parse_all_jp_dates_order():
    assert parse_all_jp_dates("2025年9月1日と2026年1月10日") == ["2025-09-01", "2026-01-10"]


@pytest.mark.parametrize("raw,expected", [
    ("月額177,000円～388,000円", 177000),
    ("17万7,000円", 177000),
    ("月額 60,000〜160,000円（地域による）", 60000),
    ("139,000円から352,000円", 139000),
    ("授業料の一部", None),
    ("", None),
])
def test_normalize_amount(raw, expected):
    assert normalize_amount(raw) == expected


def test_normalize_amount_ignores_small_numbers():
    # 「第18期」「2026年度」等の小さい数字は金額として拾わない
    assert normalize_amount("2026年度 第18期 月額80,000円") == 80000


def test_clean_text_folding():
    assert clean_text("Ａ　Ｂ\n\tＣ") == "A B C"
    assert clean_text("（大学院）", fold=False) == "（大学院）"


def test_truncate():
    s = "あ" * 250
    out = truncate(s, 200)
    assert len(out) == 200 and out.endswith("…")
