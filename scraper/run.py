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

from . import config  # noqa: F401  (副作用なし。設定の存在確認用)
from .merge import merge
from .sources.funai import FunaiSource
from .sources.jasso import JassoSource
from .sources.masason import MasasonSource
from .sources.osaka_u import OsakaUSource
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
    for cls in SOURCES:
        src = cls()
        items, status = src.run()
        results[src.name] = items
        statuses.append(status)
        mark = "ok" if status.get("ok") else "NG"
        print(f"[{mark}] {src.name}: {status.get('count', len(items))}件"
              + ("" if status.get("ok") else f"  <- {status.get('error')}"),
              file=sys.stderr)

    merged = merge(results=results, statuses=statuses, previous=previous, today=today)

    try:
        validate(merged)
    except Exception as e:  # noqa: BLE001
        print(f"[fatal] スキーマ検証に失敗。既存ファイルは更新しません: {e}", file=sys.stderr)
        return 1

    payload = json.dumps(merged, ensure_ascii=False, indent=2) + "\n"

    if dry_run:
        print(payload)
        return 0

    os.makedirs(os.path.dirname(output), exist_ok=True)
    with open(output, "w", encoding="utf-8") as fh:
        fh.write(payload)
    print(f"[done] {output} に {len(merged['scholarships'])}件を書き出しました "
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
