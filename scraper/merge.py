"""新規スクレイプ結果と前回 JSON をマージする。

方針（フェイルセーフ）:
- 成功したソース   -> 新データで置換。first_seen は前回値を引き継ぎ、last_seen=today。
- 失敗したソース   -> 前回の該当 source エントリをそのまま維持。status.ok=False + stale_since。
- 成功したが0件    -> 前回>0件なら「異常」とみなし失敗扱い（前回維持）。
- 重複排除        -> 同一 id、および (source, title, deadline) が重複したら先勝ち。
- 出力順          -> (source, id) で安定ソート（差分を最小化）。
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .models import Scholarship


def _prev_index(previous: Optional[dict]) -> Dict[str, dict]:
    out: Dict[str, dict] = {}
    if not previous:
        return out
    for it in previous.get("scholarships", []):
        if it.get("id"):
            out[it["id"]] = it
    return out


def _prev_by_source(previous: Optional[dict]) -> Dict[str, List[dict]]:
    out: Dict[str, List[dict]] = {}
    if not previous:
        return out
    for it in previous.get("scholarships", []):
        out.setdefault(it.get("source", ""), []).append(it)
    return out


def merge(
    *,
    results: Dict[str, List[Scholarship]],
    statuses: List[dict],
    previous: Optional[dict],
    today: str,
) -> dict:
    prev_items = _prev_index(previous)
    prev_src = _prev_by_source(previous)

    final_status: List[dict] = []
    scholarships: List[dict] = []
    seen_ids = set()
    seen_triples = set()

    def add(item: dict) -> None:
        key = item["id"]
        if key in seen_ids:
            return
        # 二次ガード: id が違っても「同一ソース・同一タイトル・同一の具体的締切日」なら重複とみなす
        # （締切 None 同士は別物の可能性があるので対象外）
        triple = (item.get("source"), item.get("title"), item.get("deadline"))
        if item.get("deadline") and triple in seen_triples:
            return
        seen_ids.add(key)
        if item.get("deadline"):
            seen_triples.add(triple)
        scholarships.append(item)

    for status in statuses:
        source = status["source"]
        items = results.get(source, [])
        prev_for_source = prev_src.get(source, [])

        degraded = dict(status)

        if status.get("ok") and items:
            for sc in items:
                d = sc.to_dict()
                old = prev_items.get(d["id"])
                d["first_seen"] = (old or {}).get("first_seen") or today
                d["last_seen"] = today
                add(d)
            degraded["count"] = len(items)
        else:
            # 失敗 or 0件 -> 前回を維持
            if status.get("ok") and not items and prev_for_source:
                degraded["ok"] = False
                degraded["error"] = "0 items returned (前回データを保持)"
            elif status.get("ok") and not items:
                degraded["ok"] = True  # そもそも前回も無い
                degraded["count"] = 0

            if not degraded.get("ok"):
                degraded.setdefault("stale_since", _stale_since(previous, source, today))
                for old in prev_for_source:
                    add(dict(old))

        final_status.append(degraded)

    # statuses に現れなかったが前回だけにある source も維持
    known = {s["source"] for s in statuses}
    for source, olds in prev_src.items():
        if source in known:
            continue
        final_status.append({
            "source": source,
            "ok": False,
            "error": "このソースは今回実行されませんでした（前回データを保持）",
            "stale_since": _stale_since(previous, source, today),
        })
        for old in olds:
            add(dict(old))

    scholarships.sort(key=lambda x: (x.get("source", ""), x.get("id", "")))

    return {
        "generated_at": _utc_now(),
        "source_status": final_status,
        "scholarships": scholarships,
    }


def _stale_since(previous: Optional[dict], source: str, today: str) -> str:
    if previous:
        for s in previous.get("source_status", []):
            if s.get("source") == source and s.get("stale_since"):
                return s["stale_since"]
    return today


def _utc_now() -> str:
    from datetime import datetime, timezone

    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
