"""obs/span.py — the ONE stage-boundary primitive: `with stage_span('page_selection', inputs={...}) as sp:` wraps a
pipeline stage, times it, captures inputs/outputs/confidence/validation/degradation/warnings/errors, and rolls up
every LLM call + DB query the taps attributed to it. This is how instrumentation stays UN-scattered: each stage is
wrapped ONCE at its entry function; nothing inside a stage logs by hand.

Nesting: the parent span is whatever was active in the caller's context; worker threads (run/parallel copies the
context) each get their own child slot, so per-card spans in a pool nest under the fan-out's parent span.

Exceptions are RECORDED (status='error', the error string) and RE-RAISED — the pipeline's own fail-open/reflect
semantics stay in charge; a span never swallows or alters control flow. Everything else here is fail-open."""
import time
import uuid
from contextlib import contextmanager

from obs import trace as _trace


class Span:
    """Handle the wrapped stage uses to attach results. All setters are fail-open and chainable."""

    __slots__ = ("d",)

    def __init__(self, d):
        self.d = d

    def set_inputs(self, **fields):
        self.d["inputs"] = {**(self.d.get("inputs") or {}), **fields}
        return self

    def set_outputs(self, **fields):
        self.d["outputs"] = {**(self.d.get("outputs") or {}), **fields}
        return self

    def set_confidence(self, **fields):
        """Confidence signals for THIS stage (e.g. how='AI', class_prior=0.9, page_key_how='guided')."""
        self.d["confidence"] = {**(self.d.get("confidence") or {}), **fields}
        return self

    def set_validation(self, **fields):
        self.d["validation"] = {**(self.d.get("validation") or {}), **fields}
        return self

    def set_degradation(self, **fields):
        """Stage-level degradation state (honest-blank / gap / no_data / reroute...). Also mirrored trace-level."""
        clean = {k: v for k, v in fields.items() if v is not None}
        if clean:
            self.d["degradation"] = {**(self.d.get("degradation") or {}), **clean}
            self.d["status"] = self.d["status"] if self.d["status"] == "error" else "degraded"
        return self

    def warn(self, message):
        self.d.setdefault("warnings", []).append(str(message)[:300])
        return self

    def error(self, message):
        self.d.setdefault("errors", []).append(str(message)[:500])
        self.d["status"] = "error"
        return self


def _new_span(stage, card_id, inputs, attrs):
    parent = _trace.current_span()
    return {
        "span_id": uuid.uuid4().hex[:12],
        "parent_span_id": (parent or {}).get("span_id"),
        "stage": stage,
        "card_id": card_id,
        "ts_start": time.time(),
        "ts_end": None,
        "status": "ok",
        "inputs": inputs,
        "outputs": None,
        "confidence": None,
        "validation": None,
        "degradation": None,
        "warnings": [],
        "errors": [],
        "attrs": attrs or {},
        "ai": {"n_calls": 0, "tokens_prompt": 0, "tokens_completion": 0},
        "db": {"n_queries": 0, "rows_returned": 0},
    }


@contextmanager
def stage_span(stage, *, card_id=None, inputs=None, **attrs):
    """Wrap one pipeline stage. No active trace → a no-op handle (scripts/tests untraced by default)."""
    t = _trace.current()
    if t is None:
        yield Span(_new_span(stage, card_id, inputs, attrs))   # inert: never emitted
        return
    d = _new_span(stage, card_id, inputs, attrs)
    token = _trace.set_span(d)
    try:
        yield Span(d)
    except Exception as e:
        d.setdefault("errors", []).append(f"{type(e).__name__}: {e}")
        d["status"] = "error"
        raise
    finally:
        _trace.reset_span(token)
        d["ts_end"] = time.time()
        try:
            _close(t, d)
        except Exception:
            pass


def _close(t, d):
    from obs import event, bus
    _trace.add_totals(t, stages=1,
                      llm_calls=d["ai"]["n_calls"],
                      tokens_prompt=d["ai"]["tokens_prompt"],
                      tokens_completion=d["ai"]["tokens_completion"],
                      db_queries=d["db"]["n_queries"],
                      rows_returned=d["db"]["rows_returned"],
                      errors=len(d.get("errors") or []),
                      warnings=len(d.get("warnings") or []))
    if d.get("errors"):
        with t["lock"]:
            t["errors"].extend(f"{d['stage']}: {x}" for x in d["errors"][:3])
    bus.emit(event.stage_event(t, d))


def attribute_ai(rec):
    """llm_tap → roll one LLM call onto the active span (and the trace totals when no span is active).
    Under the trace lock: a worker thread without its own child span attributes to the SHARED parent span."""
    t = _trace.current()
    if t is None:
        return None
    span = _trace.current_span()
    with t["lock"]:
        if span is not None:
            span["ai"]["n_calls"] += 1
            span["ai"]["tokens_prompt"] += rec.get("tokens_prompt") or 0
            span["ai"]["tokens_completion"] += rec.get("tokens_completion") or 0
        else:                                                  # orphan call (no span yet) — still count trace-level
            tot = t["totals"]
            tot["llm_calls"] += 1
            tot["tokens_prompt"] += rec.get("tokens_prompt") or 0
            tot["tokens_completion"] += rec.get("tokens_completion") or 0
    return span


def attribute_db(rec):
    """db_tap → roll one DB query onto the active span (and the trace totals when no span is active)."""
    t = _trace.current()
    if t is None:
        return None
    span = _trace.current_span()
    with t["lock"]:
        if span is not None:
            span["db"]["n_queries"] += 1
            span["db"]["rows_returned"] += rec.get("rows_returned") or 0
        else:
            t["totals"]["db_queries"] += 1
            t["totals"]["rows_returned"] += rec.get("rows_returned") or 0
    return span
