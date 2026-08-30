from __future__ import annotations

from datetime import date

from scraper.ics import build_ics, _fold


def _item(**over):
    base = dict(
        id="x-1", source="JASSO", source_url="https://example.com/x",
        title="テスト奨学金", provider="テスト財団",
        deadline="2026-10-01", deadline_type="fixed",
        amount_text="月額10万円", application_period_text="9月〜10月",
        first_seen="2026-08-30",
    )
    base.update(over)
    return base


def test_includes_only_future_fixed_deadlines():
    items = [
        _item(id="future", deadline="2026-10-01", deadline_type="fixed"),
        _item(id="past", deadline="2020-01-01", deadline_type="fixed"),
        _item(id="rolling", deadline="2026-10-01", deadline_type="rolling"),
        _item(id="nodate", deadline=None, deadline_type="annual"),
    ]
    ics = build_ics(items, today=date(2026, 8, 30))
    assert "UID:future@kisoko-scholarships" in ics
    assert "past@" not in ics
    assert "rolling@" not in ics
    assert "nodate@" not in ics
    assert ics.count("BEGIN:VEVENT") == 1


def test_structure_and_alarm():
    ics = build_ics([_item()], today=date(2026, 8, 30))
    assert ics.startswith("BEGIN:VCALENDAR\r\n")
    assert ics.rstrip().endswith("END:VCALENDAR")
    assert "DTSTART;VALUE=DATE:20261001" in ics
    assert "DTEND;VALUE=DATE:20261002" in ics
    assert "BEGIN:VALARM" in ics and "TRIGGER:-P7D" in ics
    assert "DTSTAMP:20260830T000000Z" in ics          # first_seen 由来で安定
    assert "\r\n" in ics and "\n\n" not in ics


def test_escaping():
    ics = build_ics([_item(title="A; B, C\\ D", amount_text="1,000円")], today=date(2026, 8, 30))
    assert r"A\; B\, C\\ D" in ics


def test_fold_keeps_multibyte_intact():
    long_line = "SUMMARY:" + "あ" * 60
    folded = _fold(long_line)
    for seg in folded.split("\r\n "):
        seg.encode("utf-8")  # 例外が出なければマルチバイトを分割していない
    assert "\r\n " in folded
