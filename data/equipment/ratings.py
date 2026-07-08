"""data/equipment/ratings.py — STREAM B: ratings/limits accessors over the LOCAL equipment schema (:5432 only).

One concern: per-asset breaker rating, RTM status bands, and the statutory voltage-deviation limit — resolved by the
asset's canonical neuract TABLE NAME (the ONLY safe id bridge; equipment.mfm.id is a different id space). Every fn is
fail-open (any DB error / missing row / duplicated table_name → None, never raises) and failures are never cached, so
callers stay byte-identical to today on any miss.

equipment_config: contracted_kw, critical_load_kw, thd_v_limit_pct, thd_i_limit_pct, demand_limit_kw,
target_efficiency_pct, nominal_voltage_v, rated_current_a, energy_target_kwh_today, subsidy_limit_* etc are 0/120 NULL
upstream BY DESIGN (CMD_V2 materialized them from core/config_defaults.py code defaults) — DO NOT WIRE. Only
voltage_statutory_deviation_pct (7/120) is exposed here. rated_kva (113/120) is deliberately NOT exposed either:
public.asset_nameplate stays the single rating authority (enrich around it, never duplicate it).

RTM provenance is explicit in the returned dict: the panel type resolves via mfm.equipment_id, which may be the
HOSTING panel of a bay meter — bands are panel-TYPE defaults for the equipment this meter is attached to, NOT a
per-meter calibration. Consumers (stream C's fact line) must say so.

B never imports stream A's bridge (parallel-safe): the breaker lookup is self-contained uniqueness-guarded SQL.
"""
from data.equipment import db as _db

# Band basis strings mirror CMD_V2's METRIC_META — semantics STATED to the AI, never applied to a reading by code.
# pf bands are DESCENDING >= (0.98 low ceiling > … > 0.85 high); a value below high_max / an absent value reads
# 'normal' in CMD_V2 — carried here as prose, not as code that bands anything.
_BAND_BASIS = {
    "kw":      "% of rated kW",
    "amp":     "% of rated kVA",
    "kvar":    "kvar/kva x100",
    "volt":    "|deviation %|",
    "pf":      "raw, DESCENDING >=",
    "i_unbal": "raw",
}

_BAND_COLS = ("low_max", "normal_max", "moderate_max", "high_max")

# successful lookups only (a no-row answer is a real DB state); DB ERRORS are never cached — the next call retries.
_CACHE = {}


def _esc(s):
    return str(s).replace("'", "''")


def _num(v):
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _text(v):
    return v if v not in (None, "") else None


def _breaker_row(asset_table):
    """The breaker row for a UNIQUELY-bridged table_name (dict) or None (no row / dup table / not an equipment
    meter). RAISES on DB error — the public wrappers split known-empty from unknown on exactly that."""
    key = ("breaker", asset_table)
    if key in _CACHE:
        return _CACHE[key]
    t = _esc(asset_table)
    rows = _db.eq_q(
        "SELECT b.rating_a, b.breaker_type, b.glb_node, b.panel_key "
        "FROM equipment.breaker b JOIN equipment.mfm m ON b.mfm_id = m.id "
        f"WHERE m.table_name = '{t}' "
        f"AND (SELECT count(*) FROM equipment.mfm m2 WHERE m2.table_name = '{t}') = 1"
    )
    out = None
    if rows:
        r = rows[0]
        out = {"rating_a": _num(r[0]), "breaker_type": _text(r[1]) or "",
               "glb_node": _text(r[2]), "panel_key": _text(r[3])}
    _CACHE[key] = out
    return out


def breaker_rating(asset_table):
    """{rating_a: float|None, breaker_type: str, glb_node: str|None, panel_key: str|None} for the feeder's breaker,
    or None (no row / duplicated table_name / DB error). rating_a stays None on the 133 unrated rows — NEVER
    defaulted (the overload denominator must be real or absent)."""
    if not asset_table:
        return None
    try:
        return _breaker_row(asset_table)
    except Exception:
        return None


def breaker_state(asset_table):
    """TRI-STATE probe for the emit-prompt filter (mirrors emit._nameplate_rated's contract):
      True  — a breaker row exists with a positive rating_a (the overload fn is offerable);
      False — KNOWN-EMPTY: no breaker row, NULL/non-positive rating, or a dup-table meter — all deterministic
              no-fill states, so hiding the fn is honest;
      None  — UNKNOWN (no table given / DB error) — unknown NEVER hides a fn (never over-filter on missing info)."""
    if not asset_table:
        return None
    try:
        r = _breaker_row(asset_table)
    except Exception:
        return None
    if r is None:
        return False
    rating = r.get("rating_a")
    return rating is not None and rating > 0


def rtm_const_key(paneltype_code, metric, band):
    """THE single key-speller for the RTM band app_config rows — shared by db/seed_equipment_ratings.sql (which
    derives the same spelling in SQL) and stream C's fact-line citations, so the spellings can never fork."""
    return f"consts.rtm_{paneltype_code}_{metric}_{band}"


def _bands_from_rows(rows):
    """rows of (metric, low_max, normal_max, moderate_max, high_max) → {metric: {…, basis}}; None-safe floats."""
    bands = {}
    for r in rows:
        metric = r[0]
        b = dict(zip(_BAND_COLS, (_num(v) for v in r[1:5])))
        b["basis"] = _BAND_BASIS.get(metric, "raw")
        bands[metric] = b
    return bands


def rtm_bands_for_asset(asset_table):
    """RTM status bands for the asset's meter: per-EQUIPMENT rows first (0/18 today — future-proof), else the
    panel-TYPE defaults via mfm.equipment_id → equipment.panel_type_id → core_paneltype.code. Returns
    {panel_type: code|None, provenance: 'equipment'|'panel_type_default', bands: {metric: {low_max, normal_max,
    moderate_max, high_max, basis}}} or None (unbridged/dup table, no equipment link, no rows, DB error).
    Band values are FACTS for the AI — code here never bands a reading."""
    row = _db.unique_mfm_row(asset_table) if asset_table else None
    if not row:
        return None
    try:
        eq_id = int(str(row.get("equipment_id")))
    except (TypeError, ValueError):
        return None
    try:
        pt = _db.eq_q(
            "SELECT pt.id, pt.code FROM equipment.equipment e "
            "JOIN equipment.core_paneltype pt ON pt.id = e.panel_type_id "
            f"WHERE e.id = {eq_id}"
        )
        band_sel = "metric, low_max, normal_max, moderate_max, high_max FROM equipment.rtm_threshold"
        rows = _db.eq_q(f"SELECT {band_sel} WHERE equipment_id = {eq_id}")
        if rows:
            return {"panel_type": _text(pt[0][1]) if pt else None, "provenance": "equipment",
                    "bands": _bands_from_rows(rows)}
        if not pt:
            return None
        pt_id, pt_code = int(str(pt[0][0])), _text(pt[0][1])
        rows = _db.eq_q(f"SELECT {band_sel} WHERE panel_type_id = {pt_id}")
        if not rows:
            return None
        return {"panel_type": pt_code, "provenance": "panel_type_default", "bands": _bands_from_rows(rows)}
    except Exception:
        return None


def voltage_deviation_pct(asset_table):
    """The statutory voltage-deviation limit (%) from equipment_config (7/120 populated) for a uniquely-bridged
    asset, else None. The ONLY equipment_config column wired besides D's fail-open `rating` read — see the module
    docstring for the 0/120-NULL columns that must stay unwired."""
    row = _db.unique_mfm_row(asset_table) if asset_table else None
    if not row:
        return None
    try:
        eq_id = int(str(row.get("equipment_id")))
    except (TypeError, ValueError):
        return None
    try:
        rows = _db.eq_q("SELECT voltage_statutory_deviation_pct FROM equipment.equipment_config "
                        f"WHERE equipment_id = {eq_id}")
    except Exception:
        return None
    return _num(rows[0][0]) if rows else None


def clear_cache():
    """Tests + operational reload (mirrors data/equipment/db.clear_cache)."""
    _CACHE.clear()
