"""config/quality_policy.py — thin reader over cmd_catalog.data_quality_policy (the threshold/register/denorm knobs).

Every meaningful-data / reversed-CT / denorm-clamp / coverage / sign threshold is an EDITABLE ROW, read here by key.
NO magic numbers in the grounding logic — value_min, denorm_epsilon, reversed_ct_import_max, meaningful_min_power_kw,
feeder_coverage_partial_pct, etc. all come from this table. [DS-01/04/05/06, VC-03/04/09]
"""
from data.db_client import q


def num(key, default=None):
    """The numeric knob for `key` (e.g. value_min=3, denorm_epsilon=1e-30), or `default` if the row is absent."""
    rows = q("cmd_catalog", f"SELECT num_value FROM data_quality_policy WHERE key='{_esc(key)}'")
    if not rows or rows[0][0] in (None, "", "NULL"):
        return default
    return float(rows[0][0])


def txt(key, default=None):
    """The text-policy knob for `key` (e.g. pf_sign_policy='magnitude_plus_leadlag'), or `default`."""
    rows = q("cmd_catalog", f"SELECT txt_value FROM data_quality_policy WHERE key='{_esc(key)}'")
    if not rows or rows[0][0] in (None, "", "NULL"):
        return default
    return rows[0][0]


def all_policy():
    """{key: {num_value, txt_value, note}} — the whole policy set (for a diagnostic dump)."""
    rows = q("cmd_catalog", "SELECT key, num_value, txt_value, note FROM data_quality_policy ORDER BY key")
    out = {}
    for k, nv, tv, note in rows:
        out[k] = {"num_value": (None if nv in (None, "", "NULL") else float(nv)),
                  "txt_value": (None if tv in (None, "", "NULL") else tv), "note": note}
    return out


def _esc(s):
    return str(s).replace("'", "''")
