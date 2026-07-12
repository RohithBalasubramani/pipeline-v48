"""config/feeder_overview.py — the feeder-overview scalar knobs that AREN'T status-band EDGES.

The single-feeder Overview page (legacy EMS .../consumers/overview/feeder.py) draws its 9 cards' STATUS bands from
the cmd_equipment DB via data/equipment/ratings.py (the planned cmd_catalog `band.overview.*` rows + config.bands
reader were never wired and were retired 2026-07-12 — see db/fix_deadend_knobs_20260712.sql), so those edges are NOT
declared here. What backend2's feeder_overview.py ALSO hardcoded — and the band surface has no home for —
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
    """The scalar feeder-overview knob for `key`, or its code default. Reads cmd_catalog.data_quality_policy (via
    config.policy_read — the one shared reader); falls back to _DEFAULTS[key] (else `default`) with the DB DOWN.
    Never raises (the reader swallows any DB failure)."""
    from config import policy_read as _pr
    return _pr.num(key, _DEFAULTS.get(key, default))
