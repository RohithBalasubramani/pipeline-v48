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
        return cause
    try:
        return t.format(**kw)
    except (KeyError, IndexError):
        # leave any unresolved placeholder literal rather than crash the reason channel
        out = t
        for k, v in kw.items():
            out = out.replace("{" + k + "}", str(v))
        return out


def all_templates():
    """{cause: template} for every configured reason."""
    rows = q("cmd_catalog", "SELECT cause, template FROM reason_template ORDER BY cause")
    return {r[0]: r[1] for r in rows}


def _esc(s):
    return str(s).replace("'", "''")
