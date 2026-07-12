"""obs/trace.py — the ONE execution-identity + trace-context concern. Mints a globally unique trace_id per pipeline
execution (uuid4 — unlike run_id, which is a REPLAY key hashed from the prompt and collides across executions), and
carries it through the whole run via contextvars. run/parallel.py copies the caller's context into every fan-out
thread, so 1a∥1b, the per-card Layer-2 emits and the executor card pool all inherit the same trace with no plumbing.

The trace object is ONE shared mutable dict (all threads see the same totals/warnings via their copied context);
mutations go through its lock. The CURRENT SPAN is a plain contextvar — each thread's copied context gets its own
span slot, so per-card child spans in worker threads nest under the span that was active when the pool was entered.

Telemetry only: everything here is fail-open and never raises into the pipeline."""
import contextvars
import threading
import time
import uuid

_TRACE = contextvars.ContextVar("obs_trace", default=None)   # the shared per-execution trace dict (or None)
_SPAN = contextvars.ContextVar("obs_span", default=None)     # the active span dict in THIS context (or None)


def new_trace(kind="run", prompt=None, asset_id=None, attrs=None):
    """Open a new trace and set it on the current context. Returns the trace dict."""
    t = {
        "trace_id": f"t_{uuid.uuid4().hex}",
        "kind": kind,                                          # 'run' | 'frame' | 'cli' | ...
        "prompt": prompt,
        "asset_id": asset_id,
        "run_ids": [],                                         # legacy replay keys bound as the run mints them
        "ts_start": time.time(),
        "seq": 0,                                              # monotonically increasing event order within the trace
        "totals": {"llm_calls": 0, "tokens_prompt": 0, "tokens_completion": 0,
                   "db_queries": 0, "rows_returned": 0, "stages": 0, "errors": 0, "warnings": 0},
        "warnings": [],
        "errors": [],
        "degradation": {},
        "attrs": dict(attrs or {}),
        "lock": threading.Lock(),
        "ended": False,
    }
    _TRACE.set(t)
    _SPAN.set(None)
    return t


def current():
    return _TRACE.get()


def current_trace_id():
    t = _TRACE.get()
    return t["trace_id"] if t else None


def current_span():
    return _SPAN.get()


def set_span(span):
    """Set the active span for THIS context; returns a token for reset (span.py owns the nesting discipline)."""
    return _SPAN.set(span)


def reset_span(token):
    try:
        _SPAN.reset(token)
    except Exception:                                          # token from another context (thread hop) — best effort
        _SPAN.set(None)


def next_seq(t):
    with t["lock"]:
        t["seq"] += 1
        return t["seq"]


def bind_run_id(run_id):
    """Attach a legacy run_id (prompt-hash replay key) to the active trace — joinable with pipeline_<rid>.jsonl et al.
    The reflect loop mints extra loopN run_ids; all of them bind to the SAME trace."""
    t = _TRACE.get()
    if not t or not run_id:
        return
    with t["lock"]:
        if run_id not in t["run_ids"]:
            t["run_ids"].append(run_id)


def current_run_id():
    t = _TRACE.get()
    if not t or not t["run_ids"]:
        return None
    return t["run_ids"][-1]


def add_totals(t, **deltas):
    with t["lock"]:
        for k, v in deltas.items():
            t["totals"][k] = t["totals"].get(k, 0) + (v or 0)


def trace_warn(message):
    t = _TRACE.get()
    if not t:
        return
    with t["lock"]:
        t["warnings"].append(str(message)[:300])
        t["totals"]["warnings"] += 1


def set_degradation(**fields):
    """Record execution-level degradation state (data_unavailable, asset_no_data, validation_blocked, ...)."""
    t = _TRACE.get()
    if not t:
        return
    with t["lock"]:
        t["degradation"].update({k: v for k, v in fields.items() if v is not None})


def end_trace(status="ok", response_summary=None):
    """Close the active trace: emit the trace-summary event (sinks upsert the obs_traces row). Idempotent, fail-open."""
    t = _TRACE.get()
    if not t or t.get("ended"):
        return None
    t["ended"] = True
    t["ts_end"] = time.time()
    t["status"] = status
    t["response_summary"] = response_summary
    try:
        from obs import event, bus
        bus.emit(event.trace_event(t))
    except Exception:
        pass
    return t
