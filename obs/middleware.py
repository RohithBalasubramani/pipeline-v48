"""obs/middleware.py — the HTTP-boundary concern: wrap one host request in a trace. Opens the globally unique
trace, emits the `request_received` marker span, runs the handler, emits the `response` span with the outcome
summary, and closes the trace (the obs_traces summary row). host/server.py calls run_traced() around each
request body — the ONLY observability line the HTTP surface needs.

The response summary is derived from the actual response dict (ok/page/cards/verdict counts/degradation), so the
trace row alone answers 'what did this execution return' without joining the stage events."""
from obs import trace as _trace
from obs.span import stage_span


def _response_summary(resp):
    try:
        if not isinstance(resp, dict):
            return {"_type": type(resp).__name__}
        cards = resp.get("cards") or []
        verdicts = {}
        for c in cards:
            v = ((c.get("render") or {}).get("verdict")) or "none"
            verdicts[v] = verdicts.get(v, 0) + 1
        return {
            "ok": resp.get("ok"),
            "kind": resp.get("kind"),
            "run_id": resp.get("run_id"),
            "page_key": (resp.get("page") or {}).get("page_key"),
            "asset": ((resp.get("asset") or {}).get("asset") or {}).get("name"),
            "n_cards": len(cards),
            "verdicts": verdicts,
            "asset_pending": resp.get("asset_pending"),
            "asset_no_data": resp.get("asset_no_data"),
            "validation_blocked": resp.get("validation_blocked"),
            "data_unavailable": resp.get("data_unavailable"),
            "elapsed_ms": resp.get("elapsed_ms"),
            "errors": resp.get("errors") or {},
        }
    except Exception:
        return None


def run_traced(kind, request_fields, fn):
    """Run `fn()` (the request handler body) inside a fresh trace. Returns fn()'s result; re-raises its
    exception AFTER closing the trace as status='error' (the HTTP 500 path stays byte-identical)."""
    try:
        _trace.new_trace(kind=kind, prompt=(request_fields or {}).get("prompt"),
                         asset_id=(request_fields or {}).get("asset_id"),
                         attrs={k: v for k, v in (request_fields or {}).items()
                                if k not in ("prompt", "asset_id") and v is not None})
        with stage_span("request_received", inputs=request_fields):
            pass                                               # instantaneous marker: the request as received
    except Exception:
        pass
    try:
        resp = fn()
    except Exception as e:
        try:
            t = _trace.current()
            if t is not None:
                with t["lock"]:
                    t["errors"].append(f"unhandled: {type(e).__name__}: {e}")
            _trace.end_trace(status="error")
        except Exception:
            pass
        raise
    try:
        # AI DECISION INSPECTOR: the response carries its execution identity so the FE can deep-link the inspector
        # to THIS run (additive; setdefault so a handler-set value always wins).
        t0 = _trace.current()
        if isinstance(resp, dict) and t0 is not None:
            resp.setdefault("trace_id", t0["trace_id"])
        summary = _response_summary(resp)
        degraded = bool(summary and (summary.get("data_unavailable") or summary.get("asset_no_data")
                                     or summary.get("validation_blocked") or summary.get("asset_pending")))
        with stage_span("response") as sp:
            if summary:
                sp.set_outputs(**summary)
            if degraded:
                sp.set_degradation(asset_pending=summary.get("asset_pending") or None,
                                   asset_no_data=summary.get("asset_no_data") or None,
                                   validation_blocked=summary.get("validation_blocked") or None,
                                   data_unavailable=summary.get("data_unavailable") or None)
        t = _trace.current()
        status = "ok"
        if (t is not None and t["errors"]) or (isinstance(resp, dict) and resp.get("errors")):
            status = "error"
        elif degraded:
            status = "degraded"
        _trace.end_trace(status=status, response_summary=summary)
    except Exception:
        pass
    return resp
