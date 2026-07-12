"""obs/llm_tap.py — the ONE LLM-call recorder. llm/client.py (the single Qwen call convention) reports each
attempt here: prompt, response, token usage (the vLLM `usage` block — previously discarded), latency and the
classified failure kind. The call is attributed to the active stage span (rolled-up counts/tokens ride the stage
event) and the FULL record ships as a kind='llm' event → obs_llm_calls, so 'show me the exact prompt+reply that
produced this card' is one indexed query. Fail-open, no-op outside a trace.

DECISION CONTEXT [AI Decision Inspector]: an AI stage declares WHAT it is deciding right before its call_qwen —
`set_decision(kind='selection', candidate_kind='page_key', candidates=[...])` — via a contextvar (run/parallel
copies the context into fan-out threads, so per-card L2 emits carry their own). llm/client.py consumes it: every
attempt's record rides the SAME decision context (a parse-retry is the same decision) and the client clears it
when the call returns, so a later un-annotated call can never inherit a stale one. `params` carries the sampling
knobs (temperature/seed/response_format/url) so the inspector can show the exact call configuration. Candidate
lists are size-bounded here (obs.llm.max_decision_bytes) with an explicit truncation marker — never unbounded."""
import contextvars
import json
import time
import uuid

_DECISION = contextvars.ContextVar("obs_llm_decision", default=None)


def _cfg(key, default):
    try:
        from config.app_config import cfg
        return cfg(key, default)
    except Exception:
        return default


def set_decision(*, kind=None, candidate_kind=None, candidates=None, **extra):
    """Declare the decision context of the NEXT LLM call on this context. kind = 'selection' | 'classification' |
    'generative'; candidates = the option set the stage materialized BEFORE prompting (list of dicts/strings).
    Extra keyword facts (class_prior, card_id, table, vocab…) ride verbatim. Never raises (telemetry only)."""
    try:
        d = {"kind": kind, "candidate_kind": candidate_kind, "candidates": candidates, **extra}
        _DECISION.set({k: v for k, v in d.items() if v is not None} or None)
    except Exception:
        pass


def clear_decision():
    try:
        _DECISION.set(None)
    except Exception:
        pass


def current_decision():
    try:
        return _DECISION.get()
    except Exception:
        return None


def _bound_decision(d, max_bytes):
    """Size-bound the decision dict: candidates halve (with an explicit marker) until the JSON fits. Shape-true —
    a truncated list SAYS how many options were dropped, so 'rejected' views are never silently incomplete."""
    if not isinstance(d, dict):
        return d
    d = dict(d)
    try:
        while True:
            if len(json.dumps(d, default=str)) <= max_bytes:
                return d
            cands = d.get("candidates")
            if isinstance(cands, list) and len(cands) > 16:
                keep = len(cands) // 2
                d["candidates"] = cands[:keep] + [f"…[truncated] {len(cands) - keep} more option(s)"]
                d["candidates_total"] = d.get("candidates_total", len(cands))
                continue
            from obs import redact
            return redact.bound(d, max_bytes)
    except Exception:
        return {"kind": d.get("kind"), "candidate_kind": d.get("candidate_kind"), "_unloggable": True}


def record(*, stage=None, system=None, user=None, response_text=None, usage=None, latency_s=None,
           finish_reason=None, attempt=0, error_kind=None, model=None, params=None, decision=None):
    """Report ONE LLM attempt (success or classified failure). `params` = the call configuration
    (temperature/seed/response_format/url/timeout); `decision` overrides the contextvar (used by direct-POST
    callers like the insight narrator — call_qwen callers rely on set_decision instead). Never raises."""
    try:
        from obs import trace as _trace, span as _span, event, bus, redact
        t = _trace.current()
        if t is None:
            return
        now = time.time()
        mx = int(_cfg("obs.llm.max_prompt_bytes", 32768) or 32768)
        mxd = int(_cfg("obs.llm.max_decision_bytes", 24576) or 24576)
        usage = usage or {}
        rec = {
            "span_id": uuid.uuid4().hex[:12],
            "stage": stage,
            "ts_start": now - (latency_s or 0.0),
            "ts_end": now,
            "model": model,
            "prompt_system": redact.bound(system, mx) if system is not None else None,
            "prompt_user": redact.bound(user, mx) if user is not None else None,
            "response": redact.bound(response_text, mx) if response_text is not None else None,
            "tokens_prompt": usage.get("prompt_tokens"),
            "tokens_completion": usage.get("completion_tokens"),
            "finish_reason": finish_reason,
            "attempt": attempt,
            "error_kind": error_kind,
            "params": redact.bound(params, 2048) if params is not None else None,
            "decision": _bound_decision(decision if decision is not None else current_decision(), mxd),
        }
        sp = _span.attribute_ai(rec)
        bus.emit(event.llm_event(t, sp, rec))
    except Exception:
        pass


def mark_failure(stage, kind, detail=""):
    """A classified LLM OUTCOME failure (parse/no_json/truncated/over_budget after retries) → a warning on the
    active span, so the stage event carries the degradation even though each attempt was already recorded."""
    try:
        from obs import trace as _trace
        sp = _trace.current_span()
        if sp is not None:
            sp.setdefault("warnings", []).append(f"llm:{kind} stage={stage or '-'} {str(detail)[:180]}")
    except Exception:
        pass
