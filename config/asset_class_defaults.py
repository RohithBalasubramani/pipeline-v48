"""config/asset_class_defaults.py — thin reader over cmd_catalog.asset_class_default (asset_category → default JSON).

Per-CLASS engineering defaults for the policy/limit knobs a per-asset nameplate row can NOT carry: statutory voltage
band, THD limits, contracted/critical fractions, UPS battery-score bands, DG service/demand knobs, target efficiency.
Ported from CMD/backend2/core/config_defaults.py:12-140 (TRANSFORMER / DISTRIBUTION_PANEL / LT_PANEL / DG / UPS).

Resolution order for any config field: per-asset nameplate row → this class default → None (honest-degrade). This layer
NEVER supplies a fabricated rated_kva — the rating denominator stays honest per-asset (V48 deliberately keeps rated_kva
NULL when unknown rather than resurrecting the old 20000-for-a-160kVA bug); the class defaults fill only DERIVED /
POLICY knobs (bands, limits, fractions) that are genuinely class-level. [RN-01/05 honest-degrade, backend2 port #12]

fail-open: a missing row OR a DB outage → the built-in _CLASS_DEFAULTS code default (this module never raises, never
blocks import), so lookups behave identically until an editable row exists.
"""
import json

from data.db_client import q

# ── per-class code defaults (the fallback when the DB row / table is absent) — ports config_defaults.py:12-140 ────────
#    rated_kva is intentionally OMITTED here: it is honest-per-asset (asset_nameplate) or None, never a class guess.
_CLASS_DEFAULTS = {
    # 2500 kVA 11kV/415V LV distribution transformers, ~0.85 pf.
    "Transformer": {
        "contracted_kw": 2000.0, "critical_load_kw": 1500.0, "contracted_frac": 0.94,
        "voltage_statutory_deviation_pct": 10.0, "current_tolerance_pct": 20.0,
        "energy_target_kwh_today": 40000.0, "target_efficiency_pct": 99.0,
        "thd_v_limit_pct": 5.0, "thd_i_limit_pct": 8.0,
        # feeder-PQ detail path limits (powerQualityMapper.ts:157-207 IEEE_519_LV_LIMITS) — per-class so mfm_config
        # gives the PQ mapper a real per-asset limit instead of forcing the IEEE-519 code default:
        "ieee_519_voltage_thd_limit_pct": 8.0, "ieee_519_current_thd_limit_pct": 8.0,
        "ieee_519_individual_harmonic_limit_pct": 8.0, "flicker_pst_limit": 1.0, "crest_factor_ideal": 1.414,
    },
    # PCC / HT distribution buses — sized to the transformer pair feeding them.
    "Distribution Panel": {
        "contracted_kw": 4000.0, "critical_load_kw": 2700.0, "contracted_frac": 0.94,
        "voltage_statutory_deviation_pct": 10.0, "current_tolerance_pct": 20.0,
        "energy_target_kwh_today": 80000.0, "target_efficiency_pct": 99.0,
        "thd_v_limit_pct": 5.0, "thd_i_limit_pct": 8.0,
        "ieee_519_voltage_thd_limit_pct": 8.0, "ieee_519_current_thd_limit_pct": 8.0,
        "ieee_519_individual_harmonic_limit_pct": 8.0, "flicker_pst_limit": 1.0, "crest_factor_ideal": 1.414,
    },
    # LT feeders / load panels — typical 500 kW outgoing feeder.
    "LT Panel": {
        "contracted_kw": 450.0, "critical_load_kw": 270.0, "contracted_frac": 0.9,
        "voltage_statutory_deviation_pct": 10.0, "current_tolerance_pct": 20.0,
        "energy_target_kwh_today": 1200.0, "target_efficiency_pct": 97.0,
        "thd_v_limit_pct": 5.0, "thd_i_limit_pct": 8.0,
        "ieee_519_voltage_thd_limit_pct": 8.0, "ieee_519_current_thd_limit_pct": 8.0,
        "ieee_519_individual_harmonic_limit_pct": 8.0, "flicker_pst_limit": 1.0, "crest_factor_ideal": 1.414,
    },
    # diesel gensets syncing onto the 11 kV DG bus, ~0.8 pf.
    "DG": {
        "contracted_kw": 808.0, "critical_load_kw": 600.0, "contracted_frac": 0.8,
        "service_interval_hours": 300.0, "service_warn_pct": 85.0, "demand_limit_kw": 1700.0,
        "voltage_statutory_deviation_pct": 5.0, "current_tolerance_pct": 20.0,
        "current_unbalance_watch_pct": 10.0,
        "energy_target_kwh_today": 8000.0, "target_efficiency_pct": 40.0,
        "thd_v_limit_pct": 5.0, "thd_i_limit_pct": 8.0,
        "ieee_519_voltage_thd_limit_pct": 8.0, "ieee_519_current_thd_limit_pct": 8.0,
        "ieee_519_individual_harmonic_limit_pct": 8.0, "flicker_pst_limit": 1.0, "crest_factor_ideal": 1.414,
    },
    # online double-conversion UPS, 415 V output, ~0.9 pf.
    "UPS": {
        "contracted_kw": 540.0, "critical_load_kw": 400.0, "contracted_frac": 0.9,
        "voltage_statutory_deviation_pct": 10.0, "current_tolerance_pct": 20.0,
        "energy_target_kwh_today": 6000.0, "target_efficiency_pct": 96.0,
        "thd_v_limit_pct": 5.0, "thd_i_limit_pct": 8.0,
        "ieee_519_voltage_thd_limit_pct": 8.0, "ieee_519_current_thd_limit_pct": 8.0,
        "ieee_519_individual_harmonic_limit_pct": 8.0, "flicker_pst_limit": 1.0, "crest_factor_ideal": 1.414,
        # battery & autonomy score-history chart bands (0-100): Ready [ready,100] · Moderate [moderate,ready]
        # · Watch [watch,moderate]; readiness_floor = the Source & Transfer "Readiness" watchpoint line.
        "ready_threshold": 60.0, "moderate_zone": 30.0, "watch_zone": 0.0, "readiness_floor": 70.0,
    },
}

# neuract asset_category / class token → the _CLASS_DEFAULTS bucket (aliases so 'APFCR', 'lt_panel', etc. all resolve).
_CATEGORY_ALIAS = {
    "transformer": "Transformer",
    "distribution panel": "Distribution Panel", "distribution_panel": "Distribution Panel",
    "pcc": "Distribution Panel", "pcc panel": "Distribution Panel", "ht panel": "Distribution Panel",
    "lt panel": "LT Panel", "lt_panel": "LT Panel", "lt": "LT Panel",
    "apfcr": "LT Panel", "apfc": "LT Panel", "bpdb": "LT Panel", "incomer": "LT Panel",
    "dg": "DG", "diesel generator": "DG", "genset": "DG",
    "ups": "UPS",
}


def _canon(asset_category):
    """Map a raw asset_category token to a _CLASS_DEFAULTS bucket key (case/space-insensitive), or the raw text."""
    if not asset_category:
        return None
    a = str(asset_category).strip()
    return _CATEGORY_ALIAS.get(a.lower(), a)


def class_default(asset_category):
    """The full default JSON dict for a class, or {} if the class is unknown. Prefers the editable DB row
    (cmd_catalog.asset_class_default.default_json), falls back to the built-in _CLASS_DEFAULTS on a missing row or DB
    outage — so behavior is identical until a row exists."""
    canon = _canon(asset_category)
    if canon is None:
        return {}
    try:
        rows = q("cmd_catalog",
                 "SELECT default_json FROM asset_class_default "
                 f"WHERE asset_category='{_esc(canon)}'")
        if rows and rows[0][0] not in (None, "", "NULL"):
            return json.loads(rows[0][0])
    except Exception:
        pass   # DB down / table absent / bad JSON → fall through to the code default (fail-open)
    return dict(_CLASS_DEFAULTS.get(canon, {}))


def class_field(asset_category, field, default=None):
    """One field's class default (e.g. contracted_kw, thd_i_limit_pct, ready_threshold), or `default` if the class has
    no configured value. Honest: returns `default` (None) rather than a cross-class guess."""
    v = class_default(asset_category).get(field)
    return v if v is not None else default


def all_class_defaults():
    """{asset_category: default_json} for every configured class (DB rows preferred, else the built-in defaults)."""
    try:
        rows = q("cmd_catalog", "SELECT asset_category, default_json FROM asset_class_default ORDER BY asset_category")
        if rows:
            out = {}
            for cat, dj in rows:
                try:
                    out[cat] = json.loads(dj) if dj not in (None, "", "NULL") else {}
                except Exception:
                    out[cat] = {}
            return out
    except Exception:
        pass
    return {k: dict(v) for k, v in _CLASS_DEFAULTS.items()}


def _esc(s):
    return str(s).replace("'", "''")
