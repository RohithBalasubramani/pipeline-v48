"""admin/trace.py — the trace viewer's data: ONE run's full story, assembled from every sink by run_id.

Sections: executions (stage timeline slices w/ derived durations), ai calls (slim rows + which execution), sql reads,
failures, notes, response summary (cards w/ verdicts + leaf coverage), validation. Stage lines are END-markers, so
`dur_ms` on a record = time since the previous record in the same execution ("since previous event" — approximate
under the 1a∥1b and per-card fan-outs). The single-AI-call detail endpoint re-reads the raw file (full bodies are
never cached)."""
import json
import os
from datetime import datetime

from admin import ai_usage, runs, store
from admin.config import iso


def _epoch(ts):
    """ai_/failures_ rows carry local-naive ISO ts; sql_/pipeline_ rows carry epoch floats. Normalize to epoch."""
    if isinstance(ts, (int, float)):
        return float(ts)
    try:
        return datetime.fromisoformat(str(ts)).timestamp()
    except (ValueError, TypeError):
        return None


def _exec_index(exec_windows, ts):
    """Which execution slice does an event at `ts` belong to? (windows = [(start, end|None)] in order)."""
    if ts is None:
        return None
    for i, (start, end) in enumerate(exec_windows):
        if ts >= start and (end is None or ts < end):
            return i
    return None


def build(rid):
    """The full Trace for one run id, or None when nothing exists for it on disk."""
    files = store.files_for(rid)
    if not files:
        return None
    execs = runs.executions(rid)
    # execution windows: [PROMPT.ts, next PROMPT.ts) — the join key for ai/sql/failures rows (their files APPEND
    # across re-runs of the same prompt). 60 s of slack before the first PROMPT catches pre-stage traffic.
    windows = []
    for i, sl in enumerate(execs):
        start = (sl[0].get("ts") or 0) - 60
        end = execs[i + 1][0].get("ts") if i + 1 < len(execs) else None
        windows.append((start, end))

    timeline = []
    for i, sl in enumerate(execs):
        prev = None
        recs = []
        for rec in sl:
            ts = rec.get("ts")
            fields = {k: v for k, v in rec.items() if k not in ("ts", "stage")}
            recs.append({"ts": iso(ts), "stage": rec.get("stage"),
                         "dur_ms": int((ts - prev) * 1000) if (prev is not None and ts is not None) else None,
                         "fields": fields})
            prev = ts if ts is not None else prev
        first, last = sl[0].get("ts"), sl[-1].get("ts")
        timeline.append({"execution": i, "started": iso(first),
                         "wall_ms": int((last - first) * 1000) if (first and last) else None,
                         "records": recs})

    ai_calls = []
    for c in ai_usage.calls_for(rid):
        ai_calls.append({**{k: c[k] for k in ("idx", "stage", "model", "ptok", "ctok", "ttok", "finish",
                                              "guided_json", "sys_head", "user_head", "resp_head", "req_chars")},
                         "ts": iso(c["ts"]), "execution": _exec_index(windows, c["ts"])})

    sql_rows = []
    for i, rec in enumerate(store.cached(files["sql"], store.jsonl) or [] if "sql" in files else []):
        ts = _epoch(rec.get("ts"))
        sql_rows.append({"idx": i, "ts": iso(ts), "execution": _exec_index(windows, ts),
                         "db": rec.get("db"), "sql": str(rec.get("sql") or "")[:500],
                         "params": rec.get("params"), "rows": rec.get("rows"), "ms": rec.get("ms"),
                         "err": rec.get("err")})

    fails = []
    for rec in (store.cached(files["failures"], store.jsonl) or []) if "failures" in files else []:
        ts = _epoch(rec.get("ts"))
        fails.append({"ts": iso(ts), "execution": _exec_index(windows, ts), "stage": rec.get("stage"),
                      "card_id": rec.get("card_id"), "reason": rec.get("reason"), "detail": rec.get("detail")})

    notes = store.cached(files["notes"], store.jdoc) if "notes" in files else None
    resp = runs.response_summary(rid)
    return {
        "run_id": rid,
        "summary": runs.summary(rid),
        "timeline": timeline,
        "ai_calls": ai_calls,
        "sql": sql_rows,
        "failures": fails,
        "notes": notes,
        "response": resp,
    }


def ai_call_detail(rid, idx):
    """The FULL request/response bodies of one LLM call — read on demand, never cached."""
    path = store.files_for(rid).get("ai")
    if not path:
        return None
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f):
            if i == idx:
                try:
                    return json.loads(line)
                except ValueError:
                    return None
    return None


def raw_response(rid):
    """The persisted /api/run response doc verbatim (bytes) — streamed to the client, never cached."""
    path = store.files_for(rid).get("response")
    if not path or not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return f.read()
