"""admin/failures_report.py — failure report + error search over failures_<run_id>.jsonl.

The failures sink is comprehensive by construction: obs/stage.py mirrors every defect-shaped stage field
(ERROR/fail/ok=False/gap/gaps) into it, and llm/client.py records classified LLM failures — so one sink answers both
"what breaks most" (aggregates) and "find this error" (substring search over reason+detail+stage)."""
from datetime import datetime

from admin import store
from admin.config import in_window, iso


def _rows(rid):
    files = store.files_for(rid)
    if "failures" not in files:
        return []
    out = []
    for rec in store.cached(files["failures"], store.jsonl) or []:
        try:
            ts = datetime.fromisoformat(str(rec.get("ts"))).timestamp()
        except (ValueError, TypeError):
            ts = None
        out.append({"run_id": rid, "ts_epoch": ts, "ts": iso(ts), "stage": rec.get("stage"),
                    "card_id": rec.get("card_id"), "reason": rec.get("reason"),
                    "detail": rec.get("detail")})
    return out


def report(t_from=None, t_to=None, reason=None, stage=None, q=None, limit=100):
    by_reason, by_stage, by_day, matched = {}, {}, {}, []
    total = 0
    needle = q.lower() if q else None
    for rid in store.run_ids():
        for r in _rows(rid):
            if not in_window(r["ts_epoch"], t_from, t_to):
                continue
            if reason and r["reason"] != reason:
                continue
            if stage and r["stage"] != stage:
                continue
            if needle and needle not in " ".join(str(r.get(k) or "") for k in ("reason", "detail", "stage")).lower():
                continue
            total += 1
            by_reason[r["reason"]] = by_reason.get(r["reason"], 0) + 1
            by_stage[r["stage"]] = by_stage.get(r["stage"], 0) + 1
            day = (r["ts"] or "unknown")[:10]
            by_day[day] = by_day.get(day, 0) + 1
            matched.append(r)
    matched.sort(key=lambda r: -(r["ts_epoch"] or 0))
    for r in matched:
        r.pop("ts_epoch", None)
    return {
        "total": total,
        "by_reason": [{"reason": k, "count": v} for k, v in sorted(by_reason.items(), key=lambda kv: -kv[1])],
        "by_stage": [{"stage": k, "count": v} for k, v in sorted(by_stage.items(), key=lambda kv: -kv[1])],
        "by_day": [{"day": k, "count": v} for k, v in sorted(by_day.items())],
        "recent": matched[:max(0, int(limit))],
    }
