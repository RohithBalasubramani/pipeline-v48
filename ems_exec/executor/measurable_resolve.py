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


def _cfg(key, default):
    try:
        from config.app_config import cfg
        return cfg(key, default)
    except Exception:
        return default


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


# ── SOURCE-ROLE WALL [DEFECT 56(b)] ───────────────────────────────────────────────────────────────────────────────────
# A voltage/current LABEL qualified by a NON-MEASURED SOURCE ROLE names a physically distinct sensing point this meter
# does NOT have. The meter measures its OWN OUTPUT — voltage_avg / current_avg ARE that measured (output) point, NOT a
# separate bypass / input / mains / utility / grid / source / incoming / line-side rail. So:
#     'Output Voltage'  → voltage_avg  (KEEP — the meter's own measured point)
#     'Bypass Voltage'  → []           (honest blank — this meter has no bypass sensor)
#     'Input/Mains/Utility/Grid/Source/Incoming/Line-side Voltage' → []  (a separate un-metered rail)
# Generic — a SOURCE-ROLE QUALIFIER SET, never a card-specific rule. Token-EXACT (word boundaries), so it never fires on
# an unrelated substring ('sourced', 'grinder', 'inputted' … don't tokenize to the role token). DB row (code-default
# mirror) measurable.nonmeasured_source_roles. Multi-word markers ('line side' / 'line-side') match an adjacent run.
#
# DEDICATED-SENSING rails ONLY [DEFECT c59 inputVoltageV]: this default set carries ONLY roles that name a physically
# distinct, DEDICATED-sensing rail this OUTPUT-metering MFM has NO column for (bypass / utility / grid / incoming /
# line-side / source). A NON-DEDICATED role — 'input' / 'line' / 'mains' — is the meter's OWN plain reading (voltage_avg
# / current_avg ARE the input/line reading), so an input* slot LEGITIMATELY fills from the bare column and must NOT be
# walled. The default therefore EXCLUDES 'input'/'mains' (they were mis-listed, silently false-blanking every input*
# leaf — the c59 inputVoltageV defect). 'source' stays (a distinct 'source-select' rail, never the plain input reading).
_NONMEASURED_SOURCE_ROLES_DEFAULT = [
    "bypass", "utility", "grid", "source", "incoming", "line side", "line-side", "lineside",
]
# NON-DEDICATED roles [DEFECT c59]: the meter's OWN plain reading. A label carrying ONLY one of these (and no dedicated
# rail role) fills from the bare voltage_avg / current_avg — the SAME `dedicated`:false roles the honest-blank gate's
# source_role_mismatch clears. Code-default carve-out; the authoritative verdict is the `dedicated`-aware authority
# below (source_role_mismatch), this list only guarantees the offline path also clears input/line/mains.
_NONDEDICATED_ROLE_MARKERS_DEFAULT = ["input", "line", "mains"]
# roles the meter DOES measure at its OWN terminals — never blocked even if a label pairs them with a rail word.
# DB-driven (measurable.measured_source_roles) with this code-default mirror: 'output' is the ONE self/measured role
# (mirrors layer2.quantity_class where is_non_output_source('output') is False). Onboard a new measured-role NAME by
# editing the row — no card-specific rule, no code change. NOT a hardcoded label set: the DB vocab is authoritative.
_MEASURED_ROLES_DEFAULT = ["output"]


def _measured_roles():
    raw = _cfg("measurable.measured_source_roles", _MEASURED_ROLES_DEFAULT)
    if not isinstance(raw, (list, tuple)) or not raw:
        raw = _MEASURED_ROLES_DEFAULT
    return {t for m in raw for t in _tokens(m)}


def _nonmeasured_source_role_markers():
    raw = _cfg("measurable.nonmeasured_source_roles", _NONMEASURED_SOURCE_ROLES_DEFAULT)
    if not isinstance(raw, (list, tuple)) or not raw:
        raw = _NONMEASURED_SOURCE_ROLES_DEFAULT
    return [tuple(_tokens(m)) for m in raw if _tokens(m)]


def _nondedicated_role_markers():
    raw = _cfg("measurable.nondedicated_source_roles", _NONDEDICATED_ROLE_MARKERS_DEFAULT)
    if not isinstance(raw, (list, tuple)) or not raw:
        raw = _NONDEDICATED_ROLE_MARKERS_DEFAULT
    return [tuple(_tokens(m)) for m in raw if _tokens(m)]


def _marker_hit(toks, seq):
    """True when the token sequence `seq` appears as an adjacent run in `toks` (token-exact, multi-word aware)."""
    if not seq:
        return False
    n = len(seq)
    for i in range(len(toks) - n + 1):
        if tuple(toks[i:i + n]) == seq:
            return True
    return False


def _is_nonmeasured_source_role(key):
    """True when the leaf/label `key` is qualified by a DEDICATED-SENSING SOURCE ROLE (bypass / utility / grid / incoming
    / line-side / source) that this OUTPUT-metering MFM has NO dedicated column for — so a voltage/current label there
    must honest-blank rather than bind the meter's OWN reading (DEFECT 56 'Average Bypass Voltage' ← voltage_avg). A
    label naming the MEASURED role ('output') is never blocked. Token-exact; never raises.

    DEDICATED-vs-NON-DEDICATED [DEFECT c59 inputVoltageV]: 'input' / 'line' / 'mains' are NON-DEDICATED roles — the
    meter's OWN plain reading (voltage_avg / current_avg ARE the input/line reading), so an input* slot LEGITIMATELY
    fills from the bare column and must NOT be walled. Only a role with its OWN distinct sensor blocks. This mirrors the
    exact `dedicated`-aware policy the honest-blank gate already uses (layer2.gates role_smear /
    quantity_class.source_role_mismatch), so the resolver and the gate agree: bypassVoltageV blanks, inputVoltageV keeps.

    AUTHORITY ORDER (DB-vocab first, then a getattr-guarded legacy backstop — this file NEVER hard-depends on a symbol
    the vocab agent may not have landed, and NEVER bakes a role label set in code):
      1. measured-role carve-out (measurable.measured_source_roles) — 'output' names the meter's own terminal → CLEAR.
      2. DEDICATED rail markers (measurable.nonmeasured_source_roles) present → BLOCK unconditionally, EVEN IF a
         non-dedicated token co-occurs (the dedicated rail wins) — the honest-blank.
      3. NON-DEDICATED markers (measurable.nondedicated_source_roles) present, no dedicated rail → CLEAR (the meter's own
         input/line/mains reading legitimately fills). Mirrors the `dedicated`:false roles the honest-blank gate's
         quantity_class.source_role_mismatch clears, so resolver and gate agree: bypassVoltageV blanks, inputVoltageV keeps.
      4. layer2.quantity_class.is_non_output_source(key) (getattr-guarded) — legacy non-dedicated-BLIND last resort,
         consulted ONLY to BLOCK a rail the DB markers missed (True → blocked). A False from it is NOT trusted to clear
         (it wrongly reports 'input' as non-output), so it can never over-blank the meter's own input/line/mains reading."""
    toks = _tokens(key)
    if not toks:
        return False
    if _measured_roles() & set(toks):
        return False                                           # 'output' is the meter's own measured terminal
    # NON-DEDICATED carve-out [DEFECT c59 inputVoltageV]: a label naming ONLY the meter's OWN plain reading (input /
    # line / mains) and NO dedicated rail role fills from the bare column — cleared FIRST so a mixed 'bypass input'
    # style label still blocks on its dedicated role below. Two agreeing authorities, either alone clears the leaf:
    #   (a) the `dedicated`-aware source_role_mismatch (getattr): a NON-dedicated 'input'/'line'/'mains' slot vs a
    #       source claiming no role returns (False, None); a DEDICATED role (bypass) returns (True, [...]).
    #   (b) the code-default non-dedicated marker set (measurable.nondedicated_source_roles) for the offline path.
    # A DEDICATED rail marker present → BLOCK unconditionally, EVEN IF a non-dedicated token co-occurs (a multi-word
    # 'line side' contains a bare 'line', 'bypass input' pairs bypass with input): the dedicated rail wins. Checked
    # FIRST so the non-dedicated carve-out below can never smuggle a dedicated-rail label past the wall.
    dedicated_hit = any(_marker_hit(toks, seq) for seq in _nonmeasured_source_role_markers())
    if dedicated_hit:
        return True
    # NON-DEDICATED carve-out [DEFECT c59 inputVoltageV]: no dedicated rail role is present, so a label naming ONLY the
    # meter's OWN plain reading (input / line / mains) fills from the bare column. Two agreeing authorities, either
    # alone clears the leaf: (a) the `dedicated`-aware source_role_mismatch (getattr) returns (False, None) for a
    # non-dedicated role; (b) the code-default non-dedicated marker set (measurable.nondedicated_source_roles) offline.
    if any(_marker_hit(toks, seq) for seq in _nondedicated_role_markers()):
        return False                                           # the meter's own input/line/mains reading legitimately fills
    # LAST RESORT (getattr-guarded): the legacy non-dedicated-BLIND is_non_output_source — trusted ONLY to BLOCK a rail
    # the marker set above missed (e.g. a future DB source_role_markers row). Reached only when NO non-dedicated marker
    # cleared the leaf, so it can never wrongly block the meter's own 'input' reading.
    try:
        from layer2 import quantity_class as _qc
        _nonout = getattr(_qc, "is_non_output_source", None)
        if callable(_nonout) and _nonout(key) is True:
            return True
    except Exception:
        pass
    return False


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
        from layer2.quantity_class import name_class
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


# ── sibling-field resolution (the fields[] scalar-mean leaf, card 40) ─────────────────────────────────────────────────
# The non-content STOPWORD tokens (articles / stat words / display units) stripped before comparing a leaf's QUANTITY
# identity to a sibling field's. DB-driven (measurable.sibling_stopwords) with this code-default mirror.
_STOPWORDS_DEFAULT = ["the", "of", "and", "per", "avg", "average", "mean", "max", "min", "peak",
                      "total", "kw", "kwh", "kva", "kvar", "kvarh", "kvah", "hz", "pct", "percent"]


def _stopwords():
    return _tokset("measurable.sibling_stopwords", _STOPWORDS_DEFAULT)


def _content_tokens(*texts):
    """The content (non-stopword, non-unit, non-stat) tokens of a set of texts — the QUANTITY identity of a leaf/field
    ('activePowerAvgKw'→{active,power}; label 'Active Power' + metric 'active_power_total_kw'→{active,power})."""
    stop = _stopwords()
    out = set()
    for t in texts:
        for tok in _tokens(t):
            if tok and tok not in stop and not tok.isdigit():
                out.add(tok)
    return out


def sibling_column_for_scalar(key, fields, unit=None):
    """The (column, quantity) an UNBOUND MEASURABLE scalar leaf should reduce, taken from a SIBLING data field that
    already binds a real column of the SAME quantity (card 40: data.activePowerAvgKw is unbound, but data.bars[*].active
    already binds active_power_total_kw, unit kW). Match = the leaf key's content tokens ⊆ a series/scalar field's content
    tokens (its metric/column/label), AND the field carries a real column, AND (when both declare a unit) the units agree.
    `quantity` = the sibling field's unit-derived dimensional quantity (config.vocab unit_quantities; kW→power) so the
    caller's _verify applies the SAME negative-power abs convention the sibling series used (else the scalar mean of a
    reversed-CT feeder's negative active power would read −188 while the bars read +190). (None, None) when no matching
    sibling exists. Purely over the emitted fields (no DB) — the caller still verifies the column is present+logged before
    filling, so an over-reach is impossible. Never raises."""
    want = _content_tokens(key)
    if not want:
        return None, None
    ku = (unit or "").strip().lower()
    best = None
    for f in (fields or []):
        if not isinstance(f, dict):
            continue
        col = f.get("column")
        if not col or (f.get("kind") or "").lower() in ("const", "text"):
            continue
        have = _content_tokens(f.get("metric"), f.get("column"), f.get("label"))
        if not want.issubset(have):
            continue
        fu = str(f.get("unit") or "").strip().lower()
        if ku and fu and ku != fu:
            continue                                           # a declared unit mismatch → not the same quantity
        # prefer the tightest match (fewest extra tokens) so 'active power' does not bind a broader 'power' field
        extra = len(have - want)
        if best is None or extra < best[3]:
            best = (col, f.get("quantity"), f, extra)
    if best is None:
        return None, None
    col, q, f, _extra = best
    if q is None:
        try:
            from ems_exec.executor.verify import _quantity_of
            q = _quantity_of(f)                                # kW→power (the SAME dimensional lookup the bars used)
        except Exception:
            q = None
    return col, q
