"""ems_exec/executor/load_factor_fill.py — POST-FILL rescue of a BLANK LOAD-FACTOR (%) leaf that the hourly-downsampled
derivation over-blanked. ONE concern, ZERO card knowledge: a derived leaf whose resolved derivation MEASURES a
'load-factor-percent' quantity over a single real POWER column (registry _QUANTITY) that stayed BLANK because the
window's hourly AVG bucketing collapsed the asset's real running samples below the energized-degeneracy floor — is
recomputed from the RAW (native-resolution) column with the SAME mean(|p|)/peak(|p|)×100 energized identity the
derivation uses, so a genuinely-loaded asset fills its real load factor instead of false-blanking.

WHY THIS EXISTS (R4 residual false-blanks, cards 70 + 71, dg_1_mfm):
  A standby genset logs ~17k raw rows/day but runs only ~1.6 h; ems_exec.data.neuract.series/bucketed date_trunc-AVG
  that into ~25 HOURLY buckets, smearing the 96 energized minutes (mean 787 kW) into ONE ~105 kW bucket + 24 near-zero
  buckets. power._energized then keeps a single energized bucket — below its min-3 degeneracy floor (1 point == its own
  peak == a meaningless 100 %) → honest-blank. But at NATIVE resolution the SAME asset has 96 energized samples and a
  robust, non-degenerate load factor (mean 787 ÷ peak 864 = 91.1 %). The blank is a DOWNSAMPLING artifact, not absent
  data — card 71's 'Average load' KPI (avgLoadPct) and card 70's 'Availability' (availabilityPct) both false-blanked.

OVER-REACH-SAFE BY CONSTRUCTION: fires ONLY on a leaf that is (1) BLANK in the completed payload, (2) whose declared
field is a `derived` load-factor-percent quantity over ONE real power column present+logged on the asset table, AND
(3) whose RAW window carries at least `load_factor_min_energized` genuinely-energized samples (above the same
energized fraction the derivation uses). An idle window (no energized raw samples — the asset really was OFF today) or
a % -of-RATED leaf (needs a nameplate, a different quantity) keeps its honest blank — this never fabricates a load
factor for absent load. Generic — no card ids, keyed on the registry quantity table + the DB; the energized fraction /
min count are the SAME app_config knobs the derivation reads. [atomic; native-resolution SQL aggregate; never raises]
"""
from __future__ import annotations

from ems_exec.data import neuract as _nx
from ems_exec.executor import measurable_resolve as _mr
from ems_exec.executor.derived import _derived_key
from ems_exec.executor.paths import _leaf_at, _set_path, _has_path


# The registry quantity a load-factor-% derivation carries (mean/peak utilisation over a single power column). A
# 'load-factor' (%-of-RATING) or 'load-percent-of-rated' quantity is EXCLUDED — those need a nameplate denominator, a
# different quantity this pure-electrical rescue must never fabricate. DB-driven (loadfactor.registry_quantity) with
# this code-default mirror; onboard a renamed derivation-registry quantity by editing the row, no code change.
_LOAD_FACTOR_QUANTITY_DEFAULT = "load-factor-percent"


def _cfg(key, default):
    try:
        from config.app_config import cfg
        return cfg(key, default)
    except Exception:
        return default


def _load_factor_quantity():
    q = _cfg("loadfactor.registry_quantity", _LOAD_FACTOR_QUANTITY_DEFAULT)
    return str(q).strip() if isinstance(q, str) and q.strip() else _LOAD_FACTOR_QUANTITY_DEFAULT


def _energized_fraction():
    """The fraction-of-peak below which a sample is STANDSTILL (excluded from the load-factor mean) — the SAME relative
    floor power.load_factor_pct uses (code default 0.02). DB-tunable so the two never diverge."""
    try:
        return float(_cfg("power.load_factor_energized_fraction", 0.02))
    except (TypeError, ValueError):
        return 0.02


def _min_energized():
    """The minimum genuinely-energized RAW samples required for a meaningful mean/peak (the SAME app_config floor the
    derivation reads; code default 3). At native resolution a real running asset clears this by orders of magnitude —
    it only guards against a lone raw blip filling a degenerate 100 %."""
    try:
        return max(1, int(_cfg("power.load_factor_min_energized", 3)))
    except (TypeError, ValueError):
        return 3


def _blank(v):
    return v is None or v == "—" or v == ""


def _load_factor_field(field):
    """The single real POWER column a `derived` field measures a load-factor-% over, or None. A field qualifies iff its
    resolved derivation's registry quantity is 'load-factor-percent' AND its base is exactly ONE non-nameplate column
    (the power series). A nameplate-denominator load factor (%-of-rated) → None (a different, rating-dependent quantity
    this rescue never fabricates)."""
    if (field.get("kind") or "raw").lower() != "derived":
        return None
    key = _derived_key(field)
    if not key:
        return None
    try:
        from config import derivation_binding as _deriv
        from ems_exec.derivations import registry as _reg
        b = _deriv.binding(key)
        fn = (b or {}).get("fn") or key
        quant = _reg._QUANTITY.get(key) or _reg._QUANTITY.get(fn)
    except Exception:
        return None
    if quant != _load_factor_quantity():
        return None
    base = [c for c in ((b or {}).get("base_columns") or []) if not str(c).startswith("nameplate:")]
    if len(base) != 1:
        return None                                             # not a single-power-column load factor
    return base[0]


def _native_load_factor(asset_table, col, window):
    """The mean(|col|)/peak(|col|)×100 load factor over the RAW rows of `window`, taken on the ENERGIZED samples only
    (|col| above the energized fraction of the window peak) — the SAME identity power.load_factor_pct applies, but at
    NATIVE resolution (no hourly AVG dilution). One SQL aggregate. None when the column is absent/unlogged, the window
    is empty, the peak is non-positive, or fewer than _min_energized() raw samples are energized (honest-blank — never a
    fabricated / degenerate load factor for an idle window)."""
    if not asset_table or not col:
        return None
    try:
        if not _nx.column_logged(asset_table, col):
            return None
    except Exception:
        return None
    frac = _energized_fraction()
    tsx = _nx._tsexpr()
    qc = _nx._qcol(col)
    conds, params = [f"{qc} IS NOT NULL"], []
    if window and window[0]:
        conds.append(f"{tsx} >= %s::timestamptz")
        params.append(str(window[0]))
    if window and window[1]:
        conds.append(f"{tsx} <= %s::timestamptz")
        params.append(str(window[1]))
    where = " WHERE " + " AND ".join(conds)
    # peak = max magnitude; energized = |p| > peak*frac; load factor = mean(energized magnitude)/peak*100.
    sql = (
        f"WITH w AS (SELECT ABS({qc}::double precision) AS p FROM {_nx._qtbl(asset_table)}{where}), "
        f"pk AS (SELECT MAX(p) AS peak FROM w) "
        f"SELECT (SELECT peak FROM pk), "
        f"AVG(w.p) FILTER (WHERE w.p > (SELECT peak FROM pk) * %s), "
        f"COUNT(*) FILTER (WHERE w.p > (SELECT peak FROM pk) * %s) "
        f"FROM w"
    )
    try:
        rows = _nx._run(sql, params + [frac, frac])
    except Exception:
        return None
    if not rows or not rows[0]:
        return None
    peak, mean_en, n_en = rows[0][0], rows[0][1], rows[0][2]
    if peak is None or mean_en is None or n_en is None:
        return None
    try:
        peak = float(peak); mean_en = float(mean_en); n_en = int(n_en)
    except (TypeError, ValueError):
        return None
    if peak <= 0 or n_en < _min_energized():
        return None                                             # idle / too-few energized raw samples → honest-blank
    lf = mean_en / peak * 100.0
    if lf != lf or lf in (float("inf"), float("-inf")):
        return None
    return round(lf, 1)


# A target slot's UNIT must be PERCENT-LIKE for a load-factor (%) to fill into it — a load-% written under an HOURS /
# COUNT / ENERGY unit is a mislabel (DEFECT 71: 91.1 load-% into {id:'total-run-hours', unit:'h', label:'Average load'}).
# Percent-like = '%' / 'pct' / 'percent' / '' (a bare/dimensionless load-factor slot). Everything else is a NON-percent
# unit → the load factor must NOT fill (a run-hours slot then honest-blanks; there is no run-hours derivation).
# DB-DRIVEN (app_config loadfactor.* rows + these code-default mirrors): edit a row to onboard a new unit token, no code
# change. The code default is authoritative until a row lands, so the DEFECT-71 tests pass on the fallback alone.
_PERCENT_UNITS_DEFAULT = ["%", "pct", "percent", "percentage", "", "-", "—"]
# Explicit NON-percent unit tokens (hours / counts / energy) — a positive block even when the unit is unfamiliar: any
# unit that carries one of these tokens is decisively not a percentage and the load factor is refused.
_NONPERCENT_UNIT_TOKENS_DEFAULT = ["h", "hr", "hrs", "hour", "hours", "count", "counts", "n", "nos", "kw", "kwh", "kva",
                                   "kvar", "kvarh", "kwhr", "mwh", "mw", "wh", "v", "a", "hz", "kwh/h", "min", "mins",
                                   "minute", "s", "sec", "day", "days"]
# NON-percent NAME tokens (id/label chrome) — the unit-absent DEFECT-71 fallback ('total-run-hours' / 'Transfers').
_NONPERCENT_NAME_TOKENS_DEFAULT = ["hours", "hour", "hrs", "hr", "runtime", "runhours", "count", "counts", "transfers",
                                   "kwh", "energy", "starts", "cycles"]


def _tokset(key, default):
    """A lowercased token SET from an app_config json/csv row, with `default` (a list) as the code-default mirror. A DB
    string value is comma/space split; a list value is used as-is. Never raises (fail-open to the default)."""
    raw = _cfg(key, default)
    if isinstance(raw, str):
        import re as _re
        raw = [t for t in _re.split(r"[,\s]+", raw) if t]
    if not isinstance(raw, (list, tuple)) or not raw:
        raw = default
    return {str(t).strip().lower() for t in raw}


def _percent_units():
    return _tokset("loadfactor.percent_units", _PERCENT_UNITS_DEFAULT)


def _nonpercent_unit_tokens():
    return _tokset("loadfactor.nonpercent_unit_tokens", _NONPERCENT_UNIT_TOKENS_DEFAULT)


def _nonpercent_name_tokens():
    return _tokset("loadfactor.nonpercent_name_tokens", _NONPERCENT_NAME_TOKENS_DEFAULT)


def _unit_is_percent_like(unit):
    """True iff `unit` is percent-like (dimensionless load-factor) — the ONLY units a load-factor-% may fill into. A
    None/absent unit is treated as percent-like (a bare load-factor KPI carries no unit); an explicit hours/count/energy
    unit is decisively rejected (DEFECT 71)."""
    if unit is None:
        return True
    u = str(unit).strip().lower()
    if u in _percent_units():
        return True
    if "%" in u or "percent" in u:
        return True
    # tokenize the unit and reject on ANY non-percent dimensional token
    import re as _re
    toks = [t for t in _re.split(r"[\s/·*]+", u) if t]
    if any(t in _nonpercent_unit_tokens() for t in toks):
        return False
    return False                                                # an unrecognized non-'%' unit is NOT percent-like


def _target_unit(out, cand, slot):
    """The load-factor target leaf's own UNIT — from a sibling `unit`/`units`/`suffix` key on the leaf's PARENT object
    (the {id, unit, label, value} tile the value leaf lives in). None when the parent carries no unit sibling."""
    from ems_exec.executor.paths import _parent_of, _toks as _tk
    # a scalar KPI value leaf: its parent object may carry the unit + id/label chrome
    parent = _parent_of(out, cand)
    if isinstance(parent, dict):
        ukeys = _mr.unit_keys()                                  # DB-driven unit-key vocab (measurable.unit_keys) — one home
        for k, v in parent.items():
            if str(k).lower() in ukeys and isinstance(v, str) and v.strip():
                return v
    return None


def _target_id_label(out, cand):
    """The (id, label) chrome of the target leaf's parent — the fallback disambiguator when the unit is absent (an id
    like 'total-run-hours' or a label naming hours/count directly still betrays a NON-load-% slot)."""
    from ems_exec.executor.paths import _parent_of
    parent = _parent_of(out, cand)
    ident = lbl = None
    if isinstance(parent, dict):
        for k, v in parent.items():
            kl = str(k).lower()
            if kl in ("id", "key", "name") and isinstance(v, str):
                ident = v
            elif kl in ("label", "title") and isinstance(v, str):
                lbl = v
    return ident, lbl


def _id_label_is_nonpercent(ident, label):
    """True when the slot's own id/label names HOURS / a COUNT / ENERGY (a NON-load-% quantity) — the unit-absent
    fallback for DEFECT 71 ('total-run-hours' / 'Run hours' / 'Transfers' names hours/count, never a load factor)."""
    import re as _re
    nonpct = _nonpercent_name_tokens()
    for text in (ident, label):
        if not text:
            continue
        toks = set(t for t in _re.split(r"[\s_\-/]+", str(text).lower()) if t)
        if toks & nonpct:
            return True
    return False


def apply(out, fields, asset_table, window, honest_blank_paths=None):
    """Fill every BLANK load-factor-% leaf of `out` from its declared column's NATIVE-resolution energized load factor.
    Returns the set of dotted leaf paths this pass filled REAL (so the caller exempts them from the unbound-gap scan).
    No-op / empty set on any failure — telemetry-safe, never raises.

    `honest_blank_paths` (optional) = the AI's EXPLICIT honest-blank path-set (fill._honest_blank_paths); a leaf here is
    SKIPPED — the AI deliberately honest-blanked it (DEFECT 56).

    UNIT GATE [DEFECT 71]: a load-factor (%) is filled ONLY into a PERCENT-LIKE target slot ('%'/'pct'/'percent'/bare).
    A load-% written under an HOURS ('h'/'hr'/'hours'), COUNT, or ENERGY unit is a mislabel — the target run-hours slot
    stays honest-blank (no run-hours derivation exists). Gated on the target leaf's sibling unit, with the leaf's own
    id/label as the unit-absent fallback."""
    filled = set()
    if not isinstance(out, dict) or not asset_table or not fields:
        return filled
    hb = honest_blank_paths or set()
    # column per field, computed at most ONCE per (column, window) — cache so sibling leaves (KPI + points) share it.
    cache: dict = {}

    def _lf_for(col):
        if col not in cache:
            cache[col] = _native_load_factor(asset_table, col, window)
        return cache[col]

    for f in fields:
        col = _load_factor_field(f)
        if not col:
            continue
        slot = f.get("slot") or f.get("target_column") or f.get("metric")
        if not slot:
            continue
        # only a SCALAR leaf (a KPI value) — never a `[*]`/series slot (a per-point load factor is a series, not a
        # single native aggregate; the wildcard/index passes own those, and a nameplate-% points slot stays blank).
        if "[*]" in slot or "[" in slot.split(".")[-1]:
            continue
        if _honest_blanked_lf(slot, hb):
            continue                                            # AI-declared honest-blank — never resurrect (DEFECT 56)
        # resolve the leaf's REAL address (the raw slot or the data.<slot> envelope the executor writes to).
        cand = next((c for c in (slot, f"data.{slot}") if _has_path(out, c)), None)
        if cand is None:
            continue                                            # no such leaf in this payload — nothing to fill
        if not _blank(_leaf_at(out, cand)):
            continue                                            # already real (the derivation filled it) — leave it
        # UNIT GATE [DEFECT 71]: refuse a NON-percent target slot (hours/count/energy) — a load-% never fills there.
        unit = _target_unit(out, cand, slot)
        if unit is not None:
            if not _unit_is_percent_like(unit):
                continue                                        # e.g. unit='h' → a run-hours slot honest-blanks
        else:
            # no unit sibling → fall back to the leaf's id/label chrome (a 'total-run-hours' id is decisively non-%)
            ident, label = _target_id_label(out, cand)
            if _id_label_is_nonpercent(ident, label):
                continue
        lf = _lf_for(col)
        if lf is None:
            continue                                            # idle / absent → honest blank stands
        _set_path(out, cand, lf)
        filled.add(slot)
        filled.add(f"data.{slot}")
    return filled


def _honest_blanked_lf(slot, hb):
    """True when `slot` matches a path the AI EXPLICITLY honest-blanked (`hb` = tokens-tuples normalized both
    address-ways by fill._honest_blank_paths; a '[*]' segment matches any index)."""
    if not hb:
        return False
    from ems_exec.executor.paths import _toks as _tk
    for form in (slot, f"data.{slot}"):
        toks = tuple(_tk(form))
        if not toks:
            continue
        if toks in hb:
            return True
        for entry in hb:
            if len(entry) == len(toks) and all(e == t or e == "*" for e, t in zip(entry, toks)):
                return True
    return False
