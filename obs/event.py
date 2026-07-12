"""obs/event.py — THE event envelope: the single place the observability record shape is defined. Four kinds share
one envelope so every sink/dashboard reads one schema:

  · kind='stage'  — one pipeline stage span (request_received … response), the workhorse record
  · kind='llm'    — one LLM call (prompt/response/tokens/latency), child of the span it ran under
  · kind='db'     — one DB query (db/sql/rows/latency), child of the span it ran under
  · kind='trace'  — the execution summary row (one per trace, written at end_trace)
  · kind='legacy' — a forwarded obs.stage.stage(...) line (old call sites, made queryable for free)

Field vocabulary (constant): trace_id, run_id, span_id, parent_span_id, seq, stage, card_id, ts_start, ts_end,
latency_ms, status, confidence, inputs, outputs, ai, db, validation, degradation, warnings, errors, attrs."""
import time

from obs import redact


from config.failopen import cfg_safe as _cfg   # THE guarded cfg reader (D3)


def _base(kind, t, *, span_id=None, parent_span_id=None, stage=None, card_id=None):
    from obs import trace as _trace
    return {
        "schema": "v48.obs.v1",
        "kind": kind,
        "trace_id": t["trace_id"] if t else None,
        "run_id": (t["run_ids"][-1] if (t and t["run_ids"]) else None),
        "span_id": span_id,
        "parent_span_id": parent_span_id,
        "seq": _trace.next_seq(t) if t else 0,
        "stage": stage,
        "card_id": card_id,
    }


def stage_event(t, span):
    """The span dict (built by obs.span) → the canonical stage event."""
    mx = int(_cfg("obs.max_field_bytes", 16384) or 16384)
    e = _base("stage", t, span_id=span["span_id"], parent_span_id=span.get("parent_span_id"),
              stage=span["stage"], card_id=span.get("card_id"))
    e.update({
        "ts_start": span["ts_start"],
        "ts_end": span["ts_end"],
        "latency_ms": int((span["ts_end"] - span["ts_start"]) * 1000),
        "status": span["status"],                              # 'ok' | 'error' | 'degraded'
        "confidence": span.get("confidence"),
        "inputs": redact.bound(span.get("inputs"), mx),
        "outputs": redact.bound(span.get("outputs"), mx),
        "ai": {"n_calls": span["ai"]["n_calls"],
               "tokens_prompt": span["ai"]["tokens_prompt"],
               "tokens_completion": span["ai"]["tokens_completion"]},
        "db": {"n_queries": span["db"]["n_queries"], "rows_returned": span["db"]["rows_returned"]},
        "validation": redact.bound(span.get("validation"), mx),
        "degradation": redact.bound(span.get("degradation"), mx),
        "warnings": [str(w)[:300] for w in span.get("warnings") or []],
        "errors": [str(x)[:500] for x in span.get("errors") or []],
        "attrs": redact.bound(span.get("attrs") or {}, 2048),
    })
    return e


def llm_event(t, span, rec):
    """One LLM call record (built by obs.llm_tap) → canonical llm event."""
    e = _base("llm", t, span_id=rec.get("span_id"), parent_span_id=(span or {}).get("span_id"),
              stage=rec.get("stage") or ((span or {}).get("stage")), card_id=(span or {}).get("card_id"))
    e.update({
        "ts_start": rec["ts_start"], "ts_end": rec["ts_end"],
        "latency_ms": int((rec["ts_end"] - rec["ts_start"]) * 1000),
        "status": "error" if rec.get("error_kind") else "ok",
        "ai": {"model": rec.get("model"),
               "prompt_system": rec.get("prompt_system"), "prompt_user": rec.get("prompt_user"),
               "response": rec.get("response"),
               "tokens_prompt": rec.get("tokens_prompt"), "tokens_completion": rec.get("tokens_completion"),
               "finish_reason": rec.get("finish_reason"), "attempt": rec.get("attempt", 0),
               "error_kind": rec.get("error_kind"),
               # DECISION INSPECTOR: the call configuration + the stage-declared decision context (candidates…),
               # both already size-bounded by llm_tap — obs_llm_calls.params / obs_llm_calls.decision.
               "params": rec.get("params"), "decision": rec.get("decision")},
        "errors": [rec["error_kind"]] if rec.get("error_kind") else [],
    })
    return e


def db_event(t, span, rec):
    """One DB query record (built by obs.db_tap) → canonical db event."""
    e = _base("db", t, span_id=rec.get("span_id"), parent_span_id=(span or {}).get("span_id"),
              stage=(span or {}).get("stage"), card_id=(span or {}).get("card_id"))
    e.update({
        "ts_start": rec["ts_start"], "ts_end": rec["ts_end"],
        "latency_ms": int((rec["ts_end"] - rec["ts_start"]) * 1000),
        "status": "error" if rec.get("error") else "ok",
        "db": {"database": rec.get("db"), "sql": rec.get("sql"),
               "rows_returned": rec.get("rows_returned")},
        "errors": [str(rec["error"])[:500]] if rec.get("error") else [],
    })
    return e


def legacy_event(t, run_id, name, fields):
    """A forwarded obs.stage.stage(run_id, name, **fields) call — the old telemetry vocabulary, now trace-linked."""
    from obs import trace as _trace
    span = _trace.current_span()
    e = _base("legacy", t, span_id=None, parent_span_id=(span or {}).get("span_id"),
              stage=f"legacy.{name}", card_id=(span or {}).get("card_id"))
    now = time.time()
    e.update({
        "ts_start": now, "ts_end": now, "latency_ms": 0,
        "status": "error" if "ERROR" in (fields or {}) else "ok",
        "outputs": redact.bound(fields, 4096),
        "errors": [str(fields["ERROR"])[:500]] if "ERROR" in (fields or {}) else [],
        "attrs": {"legacy_run_id": run_id},
    })
    return e


def trace_event(t):
    """The end-of-execution summary (one per trace)."""
    e = _base("trace", t, stage="trace")
    e.update({
        "ts_start": t["ts_start"], "ts_end": t.get("ts_end") or time.time(),
        "latency_ms": int(((t.get("ts_end") or time.time()) - t["ts_start"]) * 1000),
        "status": t.get("status", "ok"),
        "inputs": {"kind": t.get("kind"), "prompt": redact.bound(t.get("prompt"), 2048),
                   "asset_id": t.get("asset_id"), "attrs": redact.bound(t.get("attrs") or {}, 2048)},
        "outputs": redact.bound(t.get("response_summary"), 8192),
        "ai": {"n_calls": t["totals"]["llm_calls"],
               "tokens_prompt": t["totals"]["tokens_prompt"],
               "tokens_completion": t["totals"]["tokens_completion"]},
        "db": {"n_queries": t["totals"]["db_queries"], "rows_returned": t["totals"]["rows_returned"]},
        "degradation": redact.bound(t.get("degradation") or {}, 4096),
        "warnings": [str(w)[:300] for w in t.get("warnings") or []][:50],
        "errors": [str(x)[:500] for x in t.get("errors") or []][:50],
        "attrs": {"run_ids": list(t.get("run_ids") or []), "n_stages": t["totals"].get("stages", 0)},
    })
    return e
