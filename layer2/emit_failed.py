"""layer2/emit_failed.py — INFRASTRUCTURE-failure degrade: a conforming skeleton instead of a hard_fail (ONE concern).

Family split [audit 2026-07-14, 04 F1/F6]:
  · EMIT-stage gate failures (bad envelope, empty fields, real morph violations) keep today's contract —
    conforms=False, the bounded gate-retry, and the reflect page-reroute: a second chance genuinely helps there.
  · INFRASTRUCTURE failures — a per-card EXCEPTION inside run_card, or an llm-stage failure (timeout/transport) —
    degrade HERE to a CONFORMING skeleton: the card ships its real component with every data leaf honest-blank and
    a per-leaf 'emit_failed' reason. No hard_fail, no page reroute: a reroute re-runs N emits under the same
    contention that caused the timeout (the documented load-doubler) or the same code bug on a new page — proven
    pure waste (r_b190a2b43a); emit() already owns the bounded transport retry, so the "second chance" for this
    family already exists at the right level. This is the one place the per-LEAF mandate was violated in spirit.

Knob: app_config layer2.emit_failed_skeleton (code default on; seed db/seed_emit_failed_skeleton.sql). 'off'
restores the pre-2026-07-15 behavior byte-for-byte (exceptions re-raise to run/layer2_all._err; llm_err cards
stay conforms=False and reroute). Restart required on flip (cfg cache)."""


def enabled():
    try:
        from config.app_config import flag_on
        return flag_on("layer2.emit_failed_skeleton", True)
    except Exception:
        return True


def degrade(out, ci):
    """Flip a finalized llm-stage-failed output into the conforming skeleton contract. Any other output (conforming,
    emit-stage gate failure) passes through untouched. Never raises (returns `out` unchanged on any surprise)."""
    try:
        if not enabled() or not isinstance(out, dict) or out.get("conforms"):
            return out
        f = out.get("failure") or {}
        if f.get("stage") != "llm":
            return out
        di = out.get("data_instructions") or {}
        for g in (di.get("_emit_gaps") or []):
            if isinstance(g, dict):
                g["cause"] = "emit_failed"
                try:
                    from config.reason_templates import sentence
                    g["reason"] = sentence("emit_failed", metric=str(g.get("metric") or g.get("slot") or "value"))
                except Exception:
                    g["reason"] = "emit_failed"
        out["_emit_failed"] = {"stage": "llm", "reason": f.get("reason"), "detail": f.get("detail")}
        out["conforms"] = True
        out["failure"] = None
        out["answerability"] = "partial"      # the llm_err lane already forces ≥partial; pin it explicitly
        out["gap"] = False                    # an emit failure is not a DATA fact — never feeds the any_gap policy
        return out
    except Exception:
        return out


def skeleton_for_exception(run_id, card_id, l1a, l1b, exc, shared_ctx_ref=None):
    """Build the conforming skeleton for a card whose emit path RAISED: a fresh card input + a synthetic llm-error
    marker through the normal _finalize machinery (default exact_metadata, reconciled per-leaf gaps), then degrade().
    ANY failure in here re-raises the ORIGINAL exception — fail-open to the historical _err lane."""
    try:
        from layer2.build import build_card_input, _finalize
        from obs.errfmt import fmt_exc
        ci = build_card_input(run_id, card_id, l1a, l1b, shared_ctx_ref=shared_ctx_ref)
        raw = {"_llm_error": "exception", "_llm_error_detail": fmt_exc(exc)}
        out = _finalize(ci, raw, {"action": "keep"})
        out = degrade(out, ci)
        if not out.get("conforms"):
            raise exc                          # degrade didn't take (unexpected shape) — historical lane
        return out
    except Exception:
        raise exc