"""config/reason_templates.py — thin reader over cmd_catalog.reason_template (machine cause → human sentence).

The honest-blank REASON CHANNEL: a machine cause key (no_data, no_history, no_nameplate, reversed_ct, empty_feeders,
structurally_null, …) → a human template with {placeholders}. reason(cause, **kw) fills them. NO hardcoded reason
strings in logic code — every sentence is an editable row. [ER-6/2, systemic reason channel]
"""
from data.db_client import q


def template(cause):
    """The raw template string for a cause, or None if the cause has no configured template."""
    rows = q("cmd_catalog", f"SELECT template FROM reason_template WHERE cause='{_esc(cause)}'")
    return rows[0][0] if rows else None


def reason(cause, **kw):
    """The filled human sentence for `cause` (missing {placeholders} left literal, never raises). Falls back to the
    cause key itself when no template exists so the channel is never empty."""
    t = template(cause)
    if t is None:
        return _tell_failures(cause, cause)
    try:
        return _tell_failures(cause, t.format(**kw))
    except (KeyError, IndexError):
        # leave any unresolved placeholder literal rather than crash the reason channel
        out = t
        for k, v in kw.items():
            out = out.replace("{" + k + "}", str(v))
        return _tell_failures(cause, out)


def _tell_failures(cause, sentence):
    """failures fan-out [#17; fullsweep_20260706 telemetry gap: failures_ fired on 1/42 defect cards]. Every generated
    reason sentence IS a per-leaf honest-degrade recording point (fill._gap_sentence, layer2 unbound_by_emit, asset_3d
    no-model, harness degrade, …) and they ALL funnel through here — so this ONE hook mirrors the whole reason channel
    onto obs.failures (keyed by the current ai_log run id) without touching any layer's code. Telemetry only: never
    raises, always returns the sentence unchanged."""
    try:
        from obs import ai_log, failures
        failures.record("reason", cause, detail=str(sentence)[:280],
                        run_id=getattr(ai_log, "_RUN_ID", "default"))
    except Exception:
        pass
    return sentence


def all_templates():
    """{cause: template} for every configured reason."""
    rows = q("cmd_catalog", "SELECT cause, template FROM reason_template ORDER BY cause")
    return {r[0]: r[1] for r in rows}


from config.policy_read import esc as _esc  # the ONE shared SQL-quote escape  # noqa: E402
