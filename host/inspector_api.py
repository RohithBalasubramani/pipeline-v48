"""host/inspector_api.py — the AI Decision Inspector read API (consumed by host/server.py /api/inspector/*).

Postgres-first over the obs_* store (obs/query.py), per-trace JSONL fallback (outputs/logs/trace_<id>.jsonl — the
sink_jsonl file carries the SAME canonical events), so a trace stays inspectable through a DB outage. Every LLM call
is shaped through obs/decision_view.py so the FE receives, per AI decision: stage, card, model, params
(temperature/seed/response_format), prompt (system+user), candidates, selected, rejected, reasoning, confidence,
latency, token usage, attempt/error and the raw final output. [atomic: HTTP-shaping only — storage lives in obs/]"""
import glob
import json
import os

_LOGS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs", "logs")


def _jsonable(x):
    """pg rows carry datetimes/Decimals — make the structure json.dumps-safe (host/server._send uses bare dumps)."""
    if x is None or isinstance(x, (bool, int, float, str)):
        return x
    if isinstance(x, dict):
        return {str(k): _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_jsonable(v) for v in x]
    return str(x)


def _events_from_jsonl(trace_id):
    p = os.path.join(_LOGS, f"trace_{trace_id}.jsonl")
    if not os.path.isfile(p):
        return []
    out = []
    with open(p) as f:
        for line in f:
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def _llm_from_events(events):
    """kind='llm' jsonl events → the SAME row shape obs/query.llm_calls returns from pg."""
    rows = []
    for e in events:
        if e.get("kind") != "llm":
            continue
        ai = e.get("ai") or {}
        rows.append({"span_id": e.get("span_id"), "parent_span_id": e.get("parent_span_id"),
                     "stage": e.get("stage"), "card_id": e.get("card_id"), "ts": e.get("ts_start"),
                     "latency_ms": e.get("latency_ms"), "model": ai.get("model"),
                     "tokens_prompt": ai.get("tokens_prompt"), "tokens_completion": ai.get("tokens_completion"),
                     "finish_reason": ai.get("finish_reason"), "attempt": ai.get("attempt"),
                     "error_kind": ai.get("error_kind"), "prompt_system": ai.get("prompt_system"),
                     "prompt_user": ai.get("prompt_user"), "response": ai.get("response"),
                     "params": ai.get("params"), "decision": ai.get("decision")})
    return rows


def _rows_from(events, kinds):
    out = []
    for e in events:
        if e.get("kind") not in kinds:
            continue
        out.append({"seq": e.get("seq"), "kind": e.get("kind"), "stage": e.get("stage"),
                    "card_id": e.get("card_id"), "span_id": e.get("span_id"),
                    "parent_span_id": e.get("parent_span_id"), "latency_ms": e.get("latency_ms"),
                    "status": e.get("status"), "n_llm_calls": (e.get("ai") or {}).get("n_calls"),
                    "tokens_prompt": (e.get("ai") or {}).get("tokens_prompt"),
                    "tokens_completion": (e.get("ai") or {}).get("tokens_completion"),
                    "n_db_queries": (e.get("db") or {}).get("n_queries"),
                    "rows_returned": (e.get("db") or {}).get("rows_returned"),
                    "confidence": e.get("confidence"), "inputs": e.get("inputs"), "outputs": e.get("outputs"),
                    "degradation": e.get("degradation"), "warnings": e.get("warnings"), "errors": e.get("errors")})
    return sorted(out, key=lambda r: r.get("seq") or 0)


def _trace_summary_from_events(trace_id, events):
    for e in reversed(events):
        if e.get("kind") == "trace":
            ins = e.get("inputs") or {}
            return {"trace_id": trace_id, "kind": ins.get("kind"), "prompt": ins.get("prompt"),
                    "started_at": e.get("ts_start"), "latency_ms": e.get("latency_ms"),
                    "status": e.get("status"),
                    "n_llm_calls": (e.get("ai") or {}).get("n_calls"),
                    "tokens_prompt": (e.get("ai") or {}).get("tokens_prompt"),
                    "tokens_completion": (e.get("ai") or {}).get("tokens_completion"),
                    "run_ids": (e.get("attrs") or {}).get("run_ids"),
                    "response_summary": e.get("outputs"), "degradation": e.get("degradation"),
                    "errors": e.get("errors"), "source": "jsonl"}
    first = events[0] if events else {}
    return {"trace_id": trace_id, "kind": None, "prompt": ((first.get("inputs") or {}).get("prompt")),
            "started_at": first.get("ts_start"), "latency_ms": None, "status": "incomplete",
            "n_llm_calls": None, "tokens_prompt": None, "tokens_completion": None,
            "run_ids": None, "response_summary": None, "degradation": None, "errors": None, "source": "jsonl"}


def traces(n=50):
    """Newest-first execution list for the inspector's left pane. pg (obs_v_trace_summary) → jsonl scan fallback."""
    try:
        from obs.query import recent
        rows = recent(n)
        if rows:
            return _jsonable([{**r, "source": "pg"} for r in rows])
    except Exception:
        pass
    files = sorted(glob.glob(os.path.join(_LOGS, "trace_*.jsonl")), key=os.path.getmtime, reverse=True)[:n]
    out = []
    for p in files:
        tid = os.path.basename(p)[len("trace_"):-len(".jsonl")]
        try:
            out.append(_trace_summary_from_events(tid, _events_from_jsonl(tid)))
        except Exception:
            continue
    return _jsonable(out)


def trace_detail(trace_id):
    """One execution, fully inspectable: the trace summary, the stage-span tree, and EVERY AI decision (one per LLM
    attempt) shaped through obs/decision_view.view. pg-first per section, jsonl fallback per section."""
    from obs import decision_view

    events = None                                              # lazy: only read the jsonl once, only if needed
    stages, calls, summary = [], [], None
    try:
        from obs.query import trace_events
        stages = trace_events(trace_id)
    except Exception:
        stages = []
    if not stages:
        events = _events_from_jsonl(trace_id)
        stages = _rows_from(events, {"stage", "legacy"})
    try:
        from obs.query import llm_calls
        calls = llm_calls(trace_id)
    except Exception:
        calls = []
    if not calls:
        events = events if events is not None else _events_from_jsonl(trace_id)
        calls = _llm_from_events(events)
    try:
        from obs.query import _rows as _pg_rows
        rows = _pg_rows("SELECT * FROM obs_v_trace_summary WHERE trace_id = %s", (trace_id,))
        summary = rows[0] if rows else None
    except Exception:
        summary = None
    if summary is None:
        events = events if events is not None else _events_from_jsonl(trace_id)
        summary = _trace_summary_from_events(trace_id, events)

    decisions = []
    for i, c in enumerate(calls):
        d = c.get("decision")
        p = c.get("params")
        d = json.loads(d) if isinstance(d, str) else d          # pg jsonb arrives parsed via psycopg2; text-mode safe
        p = json.loads(p) if isinstance(p, str) else p
        decisions.append({
            "i": i,
            "stage": c.get("stage"), "card_id": c.get("card_id"),
            "ts": c.get("ts"), "latency_ms": c.get("latency_ms"),
            "model": c.get("model"), "params": p,
            "prompt_system": c.get("prompt_system"), "prompt_user": c.get("prompt_user"),
            "response": c.get("response"),
            "tokens_prompt": c.get("tokens_prompt"), "tokens_completion": c.get("tokens_completion"),
            "finish_reason": c.get("finish_reason"), "attempt": c.get("attempt"),
            "error_kind": c.get("error_kind"),
            "decision": decision_view.view(c.get("stage"), c.get("response"), decision=d,
                                           error_kind=c.get("error_kind")),
        })
    return _jsonable({"trace": summary, "stages": stages, "decisions": decisions})
