"""obs/errfmt.py — the ONE exception format + record helper [error-handling F4, 2026-07-12].

`f"{type(e).__name__}: {e}"` was hand-rolled at 15+ sites, and two failure channels (data/equipment stderr writes,
host/multi_asset stderr) never landed in failures_<run_id>.jsonl where every runbook looks. fmt_exc keeps the byte-
identical string; record_exc adds the missing telemetry (delegates to obs.failures.record, NEVER raises — a
telemetry failure must not take the caller down). Callers that print/stderr for operators keep doing so — record_exc
is additive. [atomic]"""


def fmt_exc(e):
    """The house exception string: 'TypeName: message' — byte-identical to the inline f-string it replaces."""
    return f"{type(e).__name__}: {e}"


def record_exc(stage, e, *, card_id=None, group_id=None, run_id="default", reason="exception"):
    """Record an exception into the failures channel (failures_<run_id>.jsonl / obs sinks). Never raises."""
    try:
        from obs.failures import record
        record(stage, reason, card_id=card_id, group_id=group_id, detail=fmt_exc(e), run_id=run_id)
    except Exception:
        pass
