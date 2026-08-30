"""締切リマインド用の iCalendar (.ics) を生成する。

- 未来の具体的な締切（deadline があり deadline_type=="fixed"）のみを VEVENT 化。
- 各 VEVENT は 7 日前の表示アラーム付き。
- DTSTAMP は first_seen 由来の固定値にして、締切データに変化が無い限り
  ファイルが変わらない（GitHub Actions の「変更時のみコミット」と整合）。
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Iterable, List

PRODID = "-//kisoko-scholarships//deadlines//JA"
CAL_NAME = "留学奨学金・補助金 締切"


def _fold(line: str) -> str:
    """RFC 5545 のライン折り返し（オクテット単位、マルチバイトを分割しない）。"""
    raw = line.encode("utf-8")
    if len(raw) <= 74:
        return line
    out: List[bytes] = []
    buf = b""
    for ch in line:
        b = ch.encode("utf-8")
        limit = 74 if not out else 73  # 継続行は先頭スペース分1バイト減
        if len(buf) + len(b) > limit:
            out.append(buf)
            buf = b
        else:
            buf += b
    out.append(buf)
    return "\r\n ".join(seg.decode("utf-8") for seg in out)


def _esc(text: str) -> str:
    return (
        (text or "")
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def _ymd(iso: str) -> str:
    return iso.replace("-", "")


def build_ics(scholarships: Iterable[dict], *, today: date | None = None) -> str:
    today = today or date.today()
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{PRODID}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{CAL_NAME}",
        "X-WR-TIMEZONE:Asia/Tokyo",
    ]

    for s in scholarships:
        deadline = s.get("deadline")
        if not deadline or s.get("deadline_type") != "fixed":
            continue
        try:
            d = date.fromisoformat(deadline)
        except ValueError:
            continue
        if d < today:
            continue

        stamp_src = s.get("first_seen") or deadline
        try:
            stamp = datetime.fromisoformat(stamp_src).strftime("%Y%m%dT000000Z")
        except ValueError:
            stamp = "20260101T000000Z"

        desc_parts = [s.get("provider") or ""]
        if s.get("amount_text"):
            desc_parts.append(s["amount_text"])
        if s.get("application_period_text"):
            desc_parts.append(s["application_period_text"])
        desc_parts.append(f"詳細: {s.get('source_url', '')}")
        desc_parts.append("※学内締切は所属学部・研究科により異なる場合があります。必ず公式情報を確認してください。")
        description = "\n".join(p for p in desc_parts if p)

        end = d + timedelta(days=1)
        title = s.get("title", "奨学金")
        block = [
            "BEGIN:VEVENT",
            f"UID:{s.get('id', 'unknown')}@kisoko-scholarships",
            f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:{_ymd(d.isoformat())}",
            f"DTEND;VALUE=DATE:{_ymd(end.isoformat())}",
            f"SUMMARY:{_esc('【留学奨学金 締切】' + title)}",
            f"DESCRIPTION:{_esc(description)}",
            f"URL:{_esc(s.get('source_url', ''))}",
            "CATEGORIES:奨学金,締切",
            "BEGIN:VALARM",
            "TRIGGER:-P7D",
            "ACTION:DISPLAY",
            f"DESCRIPTION:{_esc(title + ' の締切1週間前')}",
            "END:VALARM",
            "END:VEVENT",
        ]
        lines.extend(block)

    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(ln) for ln in lines) + "\r\n"
