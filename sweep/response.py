"""validation/response.py — the ONE /api/run response parser. EVERY field gotcha learned from live certification
lives here and nowhere else, so no analyzer ever re-discovers them the hard way:

  · picker candidates live under `asset.candidates` (NOT top-level `candidates`) — the #1 false-FAIL in early sweeps;
  · `render.verdict` (render|partial|honest_blank) is OPTIMISTIC — per-leaf truth is `render.leaf_stats` {real,data};
  · `payload_error` = a Layer-2 emit failure for that card (exception / gate detail) — the fabrication-risk signal;
  · `is_history` marks date-navigable cards; `refetch` is served ONLY for those (the /api/frame re-fetch bundle);
  · multi-asset compare tags each card `card.asset = {id,name,class}` — distinct ids = compare GROUPS;
  · knowledge/off-scope answers ride top-level `kind`/`answer`/`refused` with cards=[] (refusal => refused=True);
  · honest terminals: `data_unavailable` + `degrade` (infra outage), `asset.how='empty'` (no such asset);
  · NEVER echo raw name strings to stdout — neuract names can carry surrogates that kill the harness (ascii()).
"""
from __future__ import annotations

from typing import Any


def ascii_safe(s: Any) -> str:
    """The mandatory print-safety net (UTF-8-surrogate agent killer)."""
    return str(s if s is not None else "").encode("ascii", "replace").decode("ascii")


def parse(resp: dict) -> dict:
    """Flatten one /api/run response into the analysis record every check/report consumes."""
    r = resp or {}
    cards = r.get("cards") or []
    asset = r.get("asset") or {}
    candidates = (asset.get("candidates") or r.get("candidates") or []) if isinstance(asset, dict) else []

    real = data = undeclared = payload_errors = 0
    verdicts: dict[str, int] = {}
    card_rows = []
    for c in cards:
        rv = (c.get("render") or {}) if isinstance(c, dict) else {}
        ls = rv.get("leaf_stats") or {}
        real += int(ls.get("real") or 0)
        data += int(ls.get("data") or 0)
        undeclared += int(ls.get("undeclared") or 0)
        v = rv.get("verdict") or "none"
        verdicts[v] = verdicts.get(v, 0) + 1
        pe = c.get("payload_error")
        if pe:
            payload_errors += 1
        card_rows.append({
            "card_id": c.get("card_id"), "render_card_id": c.get("render_card_id"),
            "title": ascii_safe(c.get("title")), "is_history": bool(c.get("is_history")),
            "has_refetch": bool(c.get("refetch")), "verdict": v,
            "real": int(ls.get("real") or 0), "data": int(ls.get("data") or 0),
            "payload_error": ascii_safe(pe)[:200] if pe else None,
            "endpoint": ascii_safe(c.get("endpoint")) or None,
            "swap_origin": (c.get("swap") or {}).get("origin"),
            "asset_group": (c.get("asset") or {}).get("id"),      # multi-asset compare lane tag (None on single)
            "data_note": ascii_safe(c.get("data_note"))[:200] if c.get("data_note") else None,
            "fill_why": ascii_safe(c.get("fill_why"))[:120] if c.get("fill_why") and not c.get("fill_ok", True) else None,
        })

    groups = sorted({cr["asset_group"] for cr in card_rows if cr["asset_group"] is not None})
    resolved = asset.get("asset") if isinstance(asset.get("asset"), dict) else (asset if asset.get("name") else {})

    # outcome classification — the single vocabulary every expectation judges against
    if r.get("kind") == "off_scope" or r.get("refused"):
        outcome = "refused"
    elif r.get("kind") == "knowledge" or (r.get("answer") and not cards):
        outcome = "knowledge"
    elif (r.get("asset_no_data") or r.get("asset_pending")) and candidates:
        # the FE OPENS THE PICKER over any cards for a no-data / pending resolution (a dark meter resolves to the
        # honest no-data picker with alternatives) — classifying by cards>0 mislabeled it 'cards' [replay 00004c55ac7d]
        outcome = "picker"
    elif len(groups) >= 2:
        outcome = "compare"
    elif cards:
        outcome = "cards"
    elif candidates:
        outcome = "picker"
    elif r.get("data_unavailable"):
        outcome = "unavailable"
    else:
        outcome = "empty"

    return {
        "outcome": outcome,
        "ok_transport": bool(r.get("ok", True)),
        "run_id": r.get("run_id"),
        # page identity lives on the TOP-LEVEL `page` object (page.page_key) — cards do NOT carry it (verified on live
        # responses; reading cards[0].page_key silently zeroed the page-coverage matrix).
        "page_key": ascii_safe((r.get("page") or {}).get("page_key") if isinstance(r.get("page"), dict)
                               else r.get("page_key")) or None,
        "elapsed_ms": r.get("elapsed_ms"),
        "asset_how": asset.get("how") if isinstance(asset, dict) else None,
        "asset_name": ascii_safe(resolved.get("name")) or None,
        "asset_class": ascii_safe(resolved.get("class")) or None,
        "member_scope": resolved.get("member_scope"),
        "n_cards": len(cards), "n_candidates": len(candidates), "n_groups": len(groups),
        "groups": groups,
        "is_history_cards": [cr["card_id"] for cr in card_rows if cr["is_history"]],
        "real_leaves": real, "data_leaves": data, "undeclared_leaves": undeclared,
        "payload_errors": payload_errors,
        "fabrication_risk": payload_errors > 0,
        "verdicts": verdicts,
        "degrade": ascii_safe(r.get("degrade"))[:200] if r.get("degrade") else None,
        "data_unavailable": bool(r.get("data_unavailable")),
        "errors": [ascii_safe(e)[:200] for e in (r.get("errors") or [])][:8],
        "notes": [ascii_safe(n)[:200] for n in (r.get("notes") or [])][:8],
        "date_window": r.get("date_window"),
        "cards": card_rows,
        "knowledge_answer_head": ascii_safe(r.get("answer"))[:160] if r.get("answer") else None,
    }
