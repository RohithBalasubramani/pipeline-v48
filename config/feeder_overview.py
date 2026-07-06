"""config/feeder_overview.py — the feeder-overview scalar knobs that AREN'T status-band EDGES.

The single-feeder Overview page (ems_backend .../consumers/overview/feeder.py) draws its 9 cards' STATUS bands from
config.bands (`band.overview.*` — busbar temp / kW-load / freq-dev / phase-balance / energy-budget / voltage-dev), so
those edges are NOT re-declared here. What backend2's feeder_overview.py ALSO hardcoded — and bands.py has no home for —
are two scalar knobs this file owns:

  • the Power-Factor tri-state FLOORS (Good ≥ good, Fair ≥ fair, else Poor)  — backend2 feeder_overview._build:108
  • the voltage STATUTORY deviation limit % shown on the voltage card         — backend2 feeder_overview._voltage_card:177

Both are editable cmd_catalog.data_quality_policy rows under the `feeder_overview.` namespace, read here with a code
default that works with the DB DOWN. Mirrors config/quality_policy.py num() (thin, never-raises, code-default fallback).
Own file per the atomic-structure rule — a NEW config concern gets its OWN config/*.py, no shared __init__ edit.
[BATCH D #13 — feeder overview producer]
"""

# ── code-default fallbacks (mirror backend2 feeder_overview.py) — used verbatim when the DB row / DB is absent ────────
_DEFAULTS = {
    "feeder_overview.pf_good_min":            0.95,   # PF ≥ this → 'Good'  (backend2 _build)
    "feeder_overview.pf_fair_min":            0.90,   # PF ≥ this → 'Fair', else 'Poor'
    "feeder_overview.voltage_statutory_pct":  5.0,    # statutory |deviation| limit % on the voltage card
    "feeder_overview.meter_gap_review_kw":    50.0,   # |Σin − Σout| kW above this → SLD meter_gap_status 'Review'
}


def num(key, default=None):
    """The scalar feeder-overview knob for `key`, or its code default. Reads cmd_catalog.data_quality_policy; falls back
    to _DEFAULTS[key] (else `default`) with the DB DOWN. Never raises (the reader swallows any DB failure)."""
    fb = _DEFAULTS.get(key, default)
    rows = _q(f"SELECT num_value FROM data_quality_policy WHERE key='{_esc(key)}'")
    if not rows or rows[0][0] in (None, "", "NULL"):
        return fb
    try:
        return float(rows[0][0])
    except (TypeError, ValueError):
        return fb


# ── internals ────────────────────────────────────────────────────────────────────────────────────────────────────

def _q(sql):
    """cmd_catalog read that NEVER raises: [] on any failure (DB down / table absent) → accessors fall back. db_client.q
    imported lazily to keep this module import-safe and framework-free."""
    try:
        from data.db_client import q
        return q("cmd_catalog", sql)
    except Exception:
        return []


def _esc(s):
    return str(s).replace("'", "''")
