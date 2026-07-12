"""ems_exec/executor/degrade.py — pass-failure TELEMETRY for the executor's fail-open pipeline [error-handling F3,
2026-07-12].

Per-leaf degradation is the house rule: a post-fill pass failure must never crash the card. But fill.py's 19 silent
`except Exception: pass` blocks made a SYSTEMICALLY broken pass invisible — if yscale.apply regresses and throws on
every card, all charts silently lose y-scales and nothing reaches obs/failures (the same silent-fail-open-hides-an-
outage defect llm/client.py was hardened against). note() adds the missing telemetry WITHOUT changing control flow:
the caller keeps its try/except + fallback; note() records and NEVER raises. run_pass() is the wrapper form for new
call sites. [atomic; telemetry-additive only — payloads byte-identical]"""


def note(pass_name, e, *, card_id=None, run_id="default"):
    """Record a swallowed pass exception into the failures channel. NEVER raises (telemetry must not break the
    fail-open contract it observes)."""
    try:
        from obs.errfmt import record_exc
        record_exc(f"ems_exec.{pass_name}", e, card_id=card_id, run_id=run_id, reason="pass_exception")
    except Exception:
        pass


def run_pass(pass_name, fn, fallback, *args, **kw):
    """fn(*args, **kw) with the house fail-open contract: an exception returns `fallback` AND records telemetry."""
    try:
        return fn(*args, **kw)
    except Exception as e:
        note(pass_name, e)
        return fallback
