"""エントリポイント: 全ソース実行 -> マージ -> スキーマ検証 -> 書き出し。

使い方:
    python -m scraper.run                 # public/scholarships.json を更新
    python -m scraper.run --dry-run        # 標準出力に JSON（ファイルは変更しない）
    python -m scraper.run --output path    # 出力先を指定
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date

from . import config
from .ics import build_ics
from .merge import merge
from .sources.funai import FunaiSource
from .sources.jasso import JassoSource
from .sources.masason import MasasonSource
from .sources.osaka_u import OsakaUSource, attach_koan
from .sources.tobitate import TobitateSource
from .sources.yoshida import YoshidaSource

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUTPUT = os.path.join(ROOT, "public", "scholarships.json")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.json")

SOURCES = [
    JassoSource,
    TobitateSource,
    FunaiSource,
    YoshidaSource,
    MasasonSource,
    OsakaUSource,
]


def load_previous(path: str) -> dict | None:
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError) as e:
        print(f"[warn] 前回 JSON を読めませんでした: {e}", file=sys.stderr)
        return None


def apply_koan(results: dict, osaka, previous: dict | None) -> int:
    """阪大KOANの一覧にある全国制度（トビタテ・JASSO学位取得型）の行を、同じ回の全国カードに添付する。

    阪大の取得が失敗したとき（途中までの行は信用しない）は、前回データの同じ id の koan を引き継ぐ。
    """
    targets = [it for name in config.KOAN_ATTACH_SOURCES for it in results.get(name, [])]
    if osaka is not None and osaka.koan_links_ok:
        n = attach_koan(targets, osaka.koan_links)
        print(f"[info] 阪大KOANの掲示を全国制度 {n}件に添付", file=sys.stderr)
        return n
    prev = {d.get("id"): d for d in (previous or {}).get("scholarships", [])}
    n = 0
    for it in targets:
        old = prev.get(it.id) or {}
        if old.get("koan"):
            it.koan = dict(old["koan"])
            it.koan_posted = it.koan_posted or old.get("koan_posted")
            n += 1
    print(f"[info] 阪大の取得に失敗したため、KOAN掲示は前回分を {n}件に引き継ぎ", file=sys.stderr)
    return n


def validate(data: dict) -> None:
    import jsonschema

    with open(SCHEMA_PATH, encoding="utf-8") as fh:
        schema = json.load(fh)
    jsonschema.validate(instance=data, schema=schema)


def run(output: str, dry_run: bool) -> int:
    today = date.today().isoformat()
    previous = load_previous(output)

    results = {}
    statuses = []
    srcs = []
    for cls in SOURCES:
        src = cls()
        items, status = src.run()
        results[src.name] = items
        statuses.append(status)
        srcs.append(src)
        mark = "ok" if status.get("ok") else "NG"
        print(f"[{mark}] {src.name}: {status.get('count', len(items))}件"
              + ("" if status.get("ok") else f"  <- {status.get('error')}"),
              file=sys.stderr)

    osaka = next((s for s in srcs if isinstance(s, OsakaUSource)), None)
    apply_koan(results, osaka, previous)

    merged = merge(results=results, statuses=statuses, previous=previous, today=today)

    try:
        validate(merged)
    except Exception as e:  # noqa: BLE001
        print(f"[fatal] スキーマ検証に失敗。既存ファイルは更新しません: {e}", file=sys.stderr)
        return 1

    payload = json.dumps(merged, ensure_ascii=False, indent=2) + "\n"
    ics = build_ics(merged["scholarships"], today=date.today())
    ics_path = os.path.join(os.path.dirname(output), "deadlines.ics")
    n_events = ics.count("BEGIN:VEVENT")

    if dry_run:
        print(payload)
        print(f"--- deadlines.ics ({n_events} events) ---", file=sys.stderr)
        return 0

    os.makedirs(os.path.dirname(output), exist_ok=True)
    with open(output, "w", encoding="utf-8") as fh:
        fh.write(payload)
    with open(ics_path, "w", encoding="utf-8", newline="") as fh:
        fh.write(ics)
    print(f"[done] {output} に {len(merged['scholarships'])}件、"
          f"deadlines.ics に {n_events}件の締切を書き出しました "
          f"(generated_at={merged['generated_at']})", file=sys.stderr)
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="奨学金情報スクレイパー")
    p.add_argument("--dry-run", action="store_true", help="標準出力に JSON を出す（保存しない）")
    p.add_argument("--output", default=DEFAULT_OUTPUT, help="出力先パス")
    args = p.parse_args(argv)
    return run(args.output, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
