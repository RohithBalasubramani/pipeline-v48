"""admin/assets_log.py — asset-resolution log: how 1b resolved (or didn't resolve) each run's asset.

Layer 1b has no dedicated sink — its record IS the '1b' + 'asset_gate' stage lines (candidates, how, class_prior,
class_mismatch, pinned, no_data, decision) plus the response's asset block (name/class/mfm_id, picker candidates).
One event row per execution, aggregated by resolution `how` (AI | ambiguous | user-choice | pinned | empty)."""
from admin import runs, store
from admin.config import in_window, iso


def report(t_from=None, t_to=None, how=None, q=None, limit=200):
    by_how, by_asset, events = {}, {}, []
    needle = q.lower() if q else None
    for rid in store.run_ids():
        ts = store.last_ts(rid)
        if not in_window(ts, t_from, t_to):
            continue
        resp = runs.response_summary(rid) or {}
        for i, sl in enumerate(runs.executions(rid)):
            by_stage = {}
            for rec in sl:
                by_stage.setdefault(rec.get("stage"), rec)
            oneb = by_stage.get("1b")
            gate = by_stage.get("asset_gate") or {}
            prompt_rec = by_stage.get("PROMPT") or {}
            if not oneb:
                continue
            ev = {
                "run_id": rid, "execution": i, "ts": iso(sl[0].get("ts")),
                "prompt": resp.get("prompt") or str(prompt_rec.get("text") or "").strip("'\""),
                "asset": oneb.get("asset") or resp.get("asset_name"),
                "mfm_id": oneb.get("mfm_id") or resp.get("asset_mfm_id"),
                "asset_class": resp.get("asset_class") or oneb.get("class_prior"),
                "how": oneb.get("how"),
                "candidates": oneb.get("candidates"),
                "basket_cols": oneb.get("basket_cols"),
                "class_prior": oneb.get("class_prior"),
                "class_mismatch": oneb.get("class_mismatch"),
                "contract_problems": oneb.get("contract_problems"),
                "pinned": gate.get("pinned"), "no_data": gate.get("no_data"),
                "gate_decision": gate.get("decision"), "gate_verdict": gate.get("verdict"),
            }
            if how and ev["how"] != how:
                continue
            if needle and needle not in " ".join(str(ev.get(k) or "") for k in ("asset", "prompt", "how")).lower():
                continue
            by_how[ev["how"] or "unknown"] = by_how.get(ev["how"] or "unknown", 0) + 1
            if ev["asset"]:
                by_asset[ev["asset"]] = by_asset.get(ev["asset"], 0) + 1
            events.append(ev)
    events.sort(key=lambda e: e["ts"] or "", reverse=True)
    return {
        "by_how": [{"how": k, "count": v} for k, v in sorted(by_how.items(), key=lambda kv: -kv[1])],
        "by_asset": [{"asset": k, "count": v} for k, v in sorted(by_asset.items(), key=lambda kv: -kv[1])[:30]],
        "events": events[:max(0, int(limit))],
    }
