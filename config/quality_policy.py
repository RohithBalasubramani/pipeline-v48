"""config/quality_policy.py — thin reader over cmd_catalog.data_quality_policy (the threshold/register/denorm knobs).

Every meaningful-data / reversed-CT / denorm-clamp / coverage / sign threshold is an EDITABLE ROW, read here by key.
NO magic numbers in the grounding logic — value_min, denorm_epsilon, reversed_ct_import_max, meaningful_min_power_kw,
feeder_coverage_partial_pct, etc. all come from this table. [DS-01/04/05/06, VC-03/04/09]
"""
from data.db_client import q


def num(key, default=None):
    """The numeric knob for `key` (e.g. value_min=3, denorm_epsilon=1e-30), or `default` if the row is absent.
    app_config is consulted FIRST (the canonical scalar-knob home, config F6 2026-07-12 — type-discriminated so a
    'text' row can't serve a num read); the legacy data_quality_policy read below keeps this module's deliberate
    RAISING semantics on a dead DB (topology_policy documents wrapping it)."""
    v = _appcfg(key)
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    rows = q("cmd_catalog", f"SELECT num_value FROM data_quality_policy WHERE key='{_esc(key)}'")
    if not rows or rows[0][0] in (None, "", "NULL"):
        return default
    return float(rows[0][0])


def txt(key, default=None):
    """The text-policy knob for `key` (e.g. pf_sign_policy='magnitude_plus_leadlag'), or `default`. app_config
    first (canonical home); the legacy data_quality_policy read keeps the RAISING semantics on a dead DB."""
    v = _appcfg(key)
    if isinstance(v, str) and v.strip() not in ("", "NULL"):
        return v
    rows = q("cmd_catalog", f"SELECT txt_value FROM data_quality_policy WHERE key='{_esc(key)}'")
    if not rows or rows[0][0] in (None, "", "NULL"):
        return default
    return rows[0][0]


from config.policy_read import esc as _esc, _appcfg  # the ONE shared escape + app_config-first read  # noqa: E402
