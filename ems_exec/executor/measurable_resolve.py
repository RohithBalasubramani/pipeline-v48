"""ems_exec/executor/measurable_resolve.py — the DETERMINISTIC "false-null / unbound MEASURABLE leaf" column resolver.
ONE concern, ZERO card knowledge: given a payload leaf's OWN semantics (its camelCase key + optional unit hint), derive
the REAL neuract column that measures it and — ONLY when that column PHYSICALLY EXISTS and IS LOGGED on the asset/member
table(s) — return it so the leaf can FILL from live data instead of false-blanking.

WHY THIS EXISTS (R4 residual false-blanks, cards 18 + 40):
  · card 18 (roster) — the card_fill_recipe row (and the AI fold) declared the `worstVoltage/worstCurrent` element keys
    vAvg/vMax/vMin/amps as {"b":"null","why":"no per-window vAvg column on gic_*"} — a FALSE reason: the member gic_*_p1
    tables DO carry voltage_avg / voltage_max / voltage_min / current_avg with full non-null data. The {"b":"null"} is
    uncolonizable by the AI fold (recipe wins), so the leaf blanked with a wrong "column absent" claim.
  · card 40 (fields) — the AI emitted NO field at all for the scalar leaves data.activePowerAvgKw / reactivePowerAvgKw,
    yet active_power_total_kw / reactive_power_total_kvar exist non-null live (the sibling bars series already binds them).

The resolver is OVER-REACH-SAFE BY CONSTRUCTION: it NEVER rebinds/fills unless the derived column is BOTH present on the
schema AND carries at least one non-null value (ems_exec.data.neuract.column_logged) — a genuinely-absent or all-null
column keeps its honest blank (no fabrication, no forced fill).

The camelCase→column mapping is DATASET/PHYSICS semantics (voltage/current + avg/max/min), NOT card facts — the SAME class
of dataset convention Policy/bindings already encode. It is DB-driven (config.app_config `measurable.*` rows) with a code
default, so a new naming scheme is onboarded by editing a row, no code change. [atomic; pure derivation + a cached DB
existence check — never raises]
"""
from __future__ import annotations

import re

from ems_exec.data import neuract as _nx


from config.failopen import cfg_safe as _cfg   # THE guarded cfg reader (D3)


# ── the dataset semantic tables (DB-driven, code-default) ─────────────────────────────────────────────────────────────
# A leaf key's QUANTITY token → the neuract column-name PREFIX family. Physics, not card facts.
_QUANTITY_DEFAULT = {
    "voltage": "voltage",
    "volt": "voltage",
    "v": "voltage",
    "current": "current",
    "amps": "current",
    "amp": "current",
    "amperes": "current",
    "ampere": "current",
    "i": "current",
}
# A leaf key's STATISTIC token → the neuract column-name SUFFIX (a per-sample reduction the meter already stores).
_STAT_DEFAULT = {
    "avg": "avg",
    "average": "avg",
    "mean": "avg",
    "max": "max",
    "maximum": "max",
    "peak": "max",
    "min": "min",
    "minimum": "min",
}


def _quantity_map():
    m = _cfg("measurable.quantity_prefix", _QUANTITY_DEFAULT)
    return m if isinstance(m, dict) and m else _QUANTITY_DEFAULT


def _stat_map():
    m = _cfg("measurable.stat_suffix", _STAT_DEFAULT)
    return m if isinstance(m, dict) and m else _STAT_DEFAULT


def _tokens(key):
    """Split a camelCase / snake_case leaf key into lowercase tokens ('vAvg'→['v','avg'], 'activePowerAvgKw'→
    ['active','power','avg','kw'], 'amps'→['amps'])."""
    if not key:
        return []
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(key))
    s = s.replace("_", " ").replace("-", " ")
    return [t for t in re.split(r"\s+", s.strip().lower()) if t]


# unit tokens that are NOT part of the column name (display units) — dropped before matching a quantity. DB-driven
# (measurable.display_unit_tokens) with this code-default mirror; a new display unit is onboarded by editing the row.
_UNIT_TOKENS_DEFAULT = ["kw", "kwh", "kva", "kvar", "kvarh", "kvah", "hz", "pct", "percent", "deg"]


def _tokset(key, default):
    """A lowercased token SET from an app_config json/csv row, with `default` (a list) as the code-default mirror. A DB
    string value is comma/space split; a list value is used as-is. Never raises (fail-open to `default`)."""
    raw = _cfg(key, default)
    if isinstance(raw, str):
        raw = [t for t in re.split(r"[,\s]+", raw) if t]
    if not isinstance(raw, (list, tuple)) or not raw:
        raw = default
    return {str(t).strip().lower() for t in raw}


def _unit_tokens():
    return _tokset("measurable.display_unit_tokens", _UNIT_TOKENS_DEFAULT)


# The object KEYS that carry a leaf's display UNIT (tile {unit|units|suffix}) — the SHARED vocab the label-keyed tile
# rescue and the load-factor rescue both read to find a leaf's unit sibling. DB-driven (measurable.unit_keys) with this
# code-default mirror; ONE definition here (the dataset-semantic vocab home) so the two rescues never drift. Public.
_UNIT_KEYS_DEFAULT = ["unit", "units", "suffix"]


def unit_keys():
    return _tokset("measurable.unit_keys", _UNIT_KEYS_DEFAULT)


# Generic MAGNITUDE words a reduced-scalar leaf may name that are NOT in the voltage/current quantity_prefix map (power /
# energy / demand / load / frequency) — the scalar-mean rescue keys its 'is this a measurable reduced scalar?' predicate
# on these plus the prefix map. DB-driven (measurable.scalar_quantity_words) with this code-default mirror. Public.
_SCALAR_QUANTITY_WORDS_DEFAULT = ["power", "energy", "demand", "load", "frequency"]


def scalar_quantity_words():
    return _tokset("measurable.scalar_quantity_words", _SCALAR_QUANTITY_WORDS_DEFAULT)


# SOURCE-ROLE WALL home = executor/source_role_wall.py (monoliths F10, 2026-07-12); re-exported byte-compatibly.
from ems_exec.executor.source_role_wall import (                                          # noqa: E402,F401
    _NONMEASURED_SOURCE_ROLES_DEFAULT, _NONDEDICATED_ROLE_MARKERS_DEFAULT, _MEASURED_ROLES_DEFAULT,
    _measured_roles, _nonmeasured_source_role_markers, _nondedicated_role_markers,
    _marker_hit, _is_nonmeasured_source_role)




def _is_derived_quantity_key(key):
    """True when the leaf key names a DERIVED / DISTORTION quantity (THD / harmonic / crest-factor / flicker / k-factor —
    anything whose quantity class is NOT the raw magnitude the `v`/`i`/voltage/current prefix map serves). The quantity
    wall (layer2.quantity_class.name_class) already classes 'iThdPk'/'iThd'/'vThd' → current-thd/voltage-thd and the
    harmonic tokens → *-harmonic. A raw voltage_avg / current_avg is the WRONG quantity for such a key (an amps reading
    posing as a peak-THD %), so the resolver MUST NOT bind it — the key honest-blanks (there is no peak-THD column).

    ONLY a derived electrical-distortion class blocks; a plain 'voltage'/'current' class or an UNCLASSIFIED abbreviation
    (vAvg/amps → None, the legit card-18 rescue) still resolves normally. Never raises (a class lookup failure = not
    derived, so a genuine raw magnitude is never accidentally blocked)."""
    try:
        from domain.quantity_class import name_class   # vocabulary home (layer2.quantity_class is its facade)
        cls = name_class(key)
    except Exception:
        return False
    if not cls:
        return False
    c = str(cls).lower()
    # DB-driven distortion-class set (measurable.derived_quantity_classes): an entry starting '-' is a SUFFIX pattern
    # ('-thd' matches current-thd/voltage-thd, '-harmonic' matches *-harmonic); any other entry is an EXACT class match
    # (crest-factor / flicker / k-factor). Code-default mirror below — behavior identical until a row lands.
    for pat in _derived_quantity_classes():
        if pat.startswith("-"):
            if c.endswith(pat):
                return True
        elif c == pat:
            return True
    return False


# The quantity CLASSES (from layer2.quantity_class.name_class) that are DERIVED / DISTORTION quantities a raw
# voltage/current column must NOT bind (a %/index, not amps/volts). DB-driven (measurable.derived_quantity_classes) with
# this code-default mirror: '-' prefix = suffix pattern; otherwise an exact class. Onboard a new distortion class by
# editing the row — no second THD/harmonic vocabulary in code.
_DERIVED_QUANTITY_CLASSES_DEFAULT = ["-thd", "-harmonic", "crest-factor", "flicker", "k-factor"]


def _derived_quantity_classes():
    raw = _cfg("measurable.derived_quantity_classes", _DERIVED_QUANTITY_CLASSES_DEFAULT)
    if isinstance(raw, str):
        raw = [t for t in re.split(r"[,\s]+", raw) if t]
    if not isinstance(raw, (list, tuple)) or not raw:
        raw = _DERIVED_QUANTITY_CLASSES_DEFAULT
    return [str(t).strip().lower() for t in raw if str(t).strip()]


def candidate_columns(key, unit=None):
    """The candidate neuract column name a MEASURABLE leaf key (+ optional unit) binds to — the EXACT `<prefix>_<stat>`
    the key names, NEVER a cross-statistic substitute. Derivation only (no DB): a QUANTITY token (voltage/current, incl.
    the v/i/amps abbreviations) plus a STATISTIC token (avg/max/min) compose `<prefix>_<stat>`; a bare-quantity leaf (no
    stat) means the canonical `_avg` headline scalar. [] when no quantity token is present.

    QUANTITY-WALL GUARD [DEFECT B, card 04 iThdPk]: a THD / harmonic / distortion key ('iThdPk'/'iThd'/'vThd') carries a
    `v`/`i` prefix token BUT its quantity is current-thd / voltage-thd (a %, not amps/volts). Binding it to the raw
    voltage_avg / current_avg column would show a raw magnitude AS a distortion reading (the 265-amps-as-peak-THD fab).
    Such a key returns [] here → honest blank (there is no peak-THD column on gic_*). A plain voltage/current key is
    untouched. This reuses the ONE quantity wall (layer2.quantity_class) — no second THD vocabulary here.

    SOURCE-ROLE WALL [DEFECT 56(b), card 56 avg-bypass-v]: a voltage/current label qualified by a NON-MEASURED SOURCE
    ROLE (bypass / input / mains / utility / grid / source / incoming / line-side) names a rail this meter does not sense
    — voltage_avg / current_avg is the meter's OWN (output) measured point, not that separate rail. Returns [] → honest
    blank; a label naming the MEASURED role ('Output Voltage') passes through. A source-role QUALIFIER set, never card-specific.

    NO OVER-REACH: a `vMax` leaf whose table has no voltage_max column returns ['voltage_max'] and blanks honestly — it
    is NEVER filled with voltage_avg (that would show the average AS the maximum, a mislabel/fabrication). The single
    candidate keeps the resolver's present+logged guard the ONLY thing standing between a fill and an honest blank."""
    if _is_derived_quantity_key(key):
        return []                                              # THD/harmonic/distortion — no raw voltage/current column measures it
    # SOURCE-ROLE WALL [DEFECT 56(b)]: a bypass/input/mains/utility/grid/source/incoming/line-side voltage/current label
    # names a rail this meter does NOT sense — voltage_avg/current_avg is the meter's OWN (output) reading, not that rail.
    # 'Output Voltage' passes (output is measured); 'Bypass/Input/Mains/… Voltage' → [] (honest blank).
    if _is_nonmeasured_source_role(key):
        return []
    qmap, smap = _quantity_map(), _stat_map()
    toks = [t for t in _tokens(key) if t not in _unit_tokens()]
    prefix = next((qmap[t] for t in toks if t in qmap), None)
    if not prefix:
        return []
    stat = next((smap[t] for t in toks if t in smap), None)
    return [f"{prefix}_{stat}" if stat else f"{prefix}_avg"]   # EXACTLY the named quantity+statistic, no substitute


def resolve_column(key, tables, unit=None):
    """The FIRST candidate column for `key` that is PRESENT AND LOGGED on ANY of `tables` (a single asset table or a
    panel's member tables), else None. This is the over-reach guard: a rebind/fill happens ONLY when a real, non-null
    column truly measures the leaf. `tables` may be a str or an iterable of table names (None entries skipped). Cached
    reads (neuract.present_columns / column_logged) — never raises."""
    tabs = [tables] if isinstance(tables, str) else [t for t in (tables or []) if t]
    if not tabs:
        return None
    for col in candidate_columns(key, unit=unit):
        for t in tabs:
            try:
                if _nx.column_logged(t, col):
                    return col
            except Exception:
                continue
    return None


# SIBLING-FIELD resolution home = executor/sibling_resolve.py (monoliths F10, 2026-07-12); re-exported byte-compatibly.
from ems_exec.executor.sibling_resolve import (                                            # noqa: E402,F401
    _STOPWORDS_DEFAULT, _stopwords, _content_tokens, sibling_column_for_scalar)
