"""admin/coverage.py — per-LEAF coverage report: how much of what we served was REAL data.

Coverage in V48 means leaf_stats {real, data, undeclared} per card (validate/render_verdict) — the verdict
(render/partial/honest_blank) is telemetry, NOT a has-data signal (per-leaf degradation rule). Aggregated from the
slim response summaries by page and by day; the top blank-reasons come from the failures sink (fill-shaped reasons)."""
from admin import runs, store
from admin.config import in_window, iso

_FILL_REASONS = {"unbound_by_emit", "no_reading", "fill_gap", "column_absent", "structurally_null",
                 "derivation_unbound", "unstripped_seed", "no_nameplate", "denorm_garbage"}


def _agg():
    return {"runs": 0, "cards": 0, "real": 0, "data": 0, "undeclared": 0,
            "render": 0, "partial": 0, "honest_blank": 0}


def _add(agg, cards):
    agg["runs"] += 1
    for c in cards:
        agg["cards"] += 1
        ls = c.get("leaf_stats") or {}
        agg["real"] += ls.get("real") or 0
        agg["data"] += ls.get("data") or 0
        agg["undeclared"] += ls.get("undeclared") or 0
        v = c.get("verdict")
        if v in ("render", "partial", "honest_blank"):
            agg[v] += 1


def _pct(agg):
    agg["real_pct"] = round(100.0 * agg["real"] / agg["data"], 1) if agg["data"] else None
    return agg


def report(t_from=None, t_to=None, page_key=None):
    totals, by_page, by_day, blanks = _agg(), {}, {}, []
    reason_counts = {}
    for rid in store.run_ids():
        ts = store.last_ts(rid)
        if not in_window(ts, t_from, t_to):
            continue
        resp = runs.response_summary(rid)
        if not resp or not resp.get("cards"):
            continue
        if page_key and resp.get("page_key") != page_key:
            continue
        cards = resp["cards"]
        _add(totals, cards)
        _add(by_page.setdefault(resp.get("page_key") or "unknown", _agg()), cards)
        _add(by_day.setdefault((iso(ts) or "unknown")[:10], _agg()), cards)
        for c in cards:
            if c.get("verdict") == "honest_blank":
                blanks.append({"run_id": rid, "card_id": c.get("card_id"), "title": c.get("title"),
                               "reason": c.get("reason"), "page_key": resp.get("page_key")})
        files = store.files_for(rid)
        for rec in (store.cached(files["failures"], store.jsonl) or []) if "failures" in files else []:
            r = rec.get("reason")
            if r in _FILL_REASONS:
                reason_counts[r] = reason_counts.get(r, 0) + 1
    return {
        "totals": _pct(totals),
        "by_page": [{"page_key": k, **_pct(v)} for k, v in sorted(by_page.items(), key=lambda kv: -kv[1]["cards"])],
        "by_day": [{"day": k, **_pct(v)} for k, v in sorted(by_day.items())],
        "honest_blanks": blanks[:100],
        "top_blank_reasons": [{"reason": k, "count": v}
                              for k, v in sorted(reason_counts.items(), key=lambda kv: -kv[1])],
    }
