"""admin/ai_usage.py — AI usage: slim per-call extraction from ai_<run_id>.jsonl (cached) + token/call aggregates.

The legacy ai_* records carry FULL request/response bodies (MBs) and NO stage/latency — so this module extracts a
small per-call row once per file version (admin/store.cached) and attributes each call to a pipeline stage by its
system-prompt head (the seven stable prompt identities below). Token counts come from the raw vLLM `usage` block —
the only place the pipeline records them. Full bodies are served ONLY by the single-call detail endpoint (trace.py)."""
from datetime import datetime

from admin import store
from admin.config import in_window, iso

# system-prompt head → stage label (checked in order; first hit wins)
STAGE_MARKERS = [
    ("You are LAYER 2", "l2_emit"),
    ("STORYTELLING ROUTER", "1a.route"),
    ("per-card ANALYTICAL STORY", "1a.stories"),
    ("ASSET RESOLVER", "1b.asset_resolve"),
    ("COLUMN RESOLVER", "1b.columns"),
    ("EMS ASSISTANT gate", "knowledge"),
    ("AI SUMMARY line", "narrative"),
]
_PREVIEW = 240


def _stage_label(system_head):
    for marker, label in STAGE_MARKERS:
        if marker in system_head:
            return label
    return "llm"


def _ts_epoch(s):
    try:
        return datetime.fromisoformat(str(s)).timestamp()
    except (ValueError, TypeError):
        return None


def _extract(path):
    """One slim row per LLM call: [{idx, ts, run_id, stage, model, ptok, ctok, ttok, finish, guided_json, sys_head,
    user_head, resp_head, req_chars}]."""
    rows = []
    for idx, rec in enumerate(store.jsonl(path)):
        req = rec.get("request") or {}
        resp = rec.get("response") or {}
        msgs = req.get("messages") or []
        system = next((m.get("content", "") for m in msgs if m.get("role") == "system"), "")
        user = next((m.get("content", "") for m in msgs if m.get("role") == "user"), "")
        choice = ((resp.get("choices") or [{}])[0]) or {}
        usage = resp.get("usage") or {}
        content = ((choice.get("message") or {}).get("content", "")) or ""
        rows.append({
            "idx": idx,
            "ts": _ts_epoch(rec.get("ts")),
            "run_id": rec.get("run_id"),
            "stage": _stage_label(system[:120]),
            "model": req.get("model") or resp.get("model"),
            "ptok": usage.get("prompt_tokens"),
            "ctok": usage.get("completion_tokens"),
            "ttok": usage.get("total_tokens"),
            "finish": choice.get("finish_reason"),
            "guided_json": bool(req.get("response_format")),
            "sys_head": system[:_PREVIEW],
            "user_head": user[:_PREVIEW],
            "resp_head": content[:_PREVIEW],
            "req_chars": len(system) + len(user),
        })
    return rows


def calls_for(rid):
    """Slim call rows for one run id ([] when it has no ai file)."""
    path = store.files_for(rid).get("ai")
    return (store.cached(path, _extract) or []) if path else []


def tokens_for(rid):
    """(n_calls, prompt_tokens, completion_tokens) totals for one run."""
    calls = calls_for(rid)
    return (len(calls),
            sum(c["ptok"] or 0 for c in calls),
            sum(c["ctok"] or 0 for c in calls))


def report(t_from=None, t_to=None, heaviest_n=20):
    """Usage aggregates across all real runs in the window: totals, by_day, by_stage, by_model, heaviest calls."""
    totals = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "runs": 0}
    by_day, by_stage, by_model, heavy = {}, {}, {}, []
    for rid in store.run_ids():
        calls = [c for c in calls_for(rid) if in_window(c["ts"], t_from, t_to)]
        if not calls:
            continue
        totals["runs"] += 1
        for c in calls:
            ptok, ctok, ttok = c["ptok"] or 0, c["ctok"] or 0, c["ttok"] or 0
            totals["calls"] += 1
            totals["prompt_tokens"] += ptok
            totals["completion_tokens"] += ctok
            totals["total_tokens"] += ttok
            day = iso(c["ts"])[:10] if c["ts"] else "unknown"
            for bucket, key in ((by_day, day), (by_stage, c["stage"]), (by_model, c["model"] or "unknown")):
                agg = bucket.setdefault(key, {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0})
                agg["calls"] += 1
                agg["prompt_tokens"] += ptok
                agg["completion_tokens"] += ctok
            heavy.append({"run_id": rid, "idx": c["idx"], "ts": iso(c["ts"]), "stage": c["stage"],
                          "ttok": ttok, "ptok": ptok, "ctok": ctok, "finish": c["finish"],
                          "sys_head": c["sys_head"][:80]})
    heavy.sort(key=lambda h: -(h["ttok"] or 0))
    return {
        "totals": totals,
        "by_day": [{"day": d, **v} for d, v in sorted(by_day.items())],
        "by_stage": [{"stage": s, **v} for s, v in sorted(by_stage.items(), key=lambda kv: -kv[1]["calls"])],
        "by_model": [{"model": m, **v} for m, v in sorted(by_model.items(), key=lambda kv: -kv[1]["calls"])],
        "heaviest": heavy[:heaviest_n],
    }
