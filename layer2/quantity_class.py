"""layer2/quantity_class.py — the PHYSICAL-QUANTITY class vocabulary + compatibility test + const-source resolver.
ONE atomic concern: classify a payload SLOT path / a basket COLUMN / a derivation FN NAME to its mutually-exclusive
physical quantity class (temperature / power / energy / current / voltage / frequency / lifetime / duration / count /
readiness / crest-factor / flicker / voltage-harmonic / current-thd / …), so that

  · the emit CONTEXT can show each basket column's quantity (qty=) and each data slot's EXPECTED quantity,
  · the emit GATE (layer2/gates.enforce_honest_blank) can blank a cross-quantity bind (power is NOT temperature /
    aging / readiness / count; a deviation/spread column is NEVER crest-factor/flicker) — the leaf honest-blanks
    with a per-leaf reason instead of shipping a fabricated number,
  · a kind=const NUMERIC field is kept ONLY when its value resolves to a REAL DB source (an asset_nameplate rating
    via config.nameplate_slot_map, or a cmd_catalog app_config `consts.*` row whose value it equals).

DB-config-driven with code-default mirrors (mandate): the vocabularies are cmd_catalog app_config rows
  quantity.unit_classes   — unit token → class ('°C'→temperature, 'A'→current, 'min'→duration, …)
  quantity.name_classes   — name token / adjacent-token-pair → class (hotspot→temperature, h5→voltage-harmonic,
                            thd+current→current-thd, faa→aging-factor, …)
  quantity.weak_classes   — dimension-only classes ('percent') too generic to flag a mismatch on
  quantity.semantic_families — NAME-level families (efficiency / sfc / consumption / fuel): a slot whose name claims
                            a family binds only a same-family (or family-licensed-class) source — the card-65
                            same-dimension pun wall ('Efficiency' ← loadFactorPct)
  quantity.compatible_slot_source_pairs — ORDERED (slot, source) grants: a statistic-kind source into its base
                            dimension's slot (amps cell ← deviation-spread stat) — reverse NOT granted
  quantity.structural_const_tokens — const metric/leaf tokens that name DISPLAY knobs (decimals/opacity/index/
                            layout/windowDays), exempt from the const-source guard (they state no measurement)
seeded by db/seed_quantity_class.sql; the code defaults below behave identically until a row exists. Generic — NO
card / slot / asset ids; token-exact matching (never substring) so 'graph5' can never read as 'h5'. A name that
classifies on NEITHER side returns None and callers MUST treat None as "don't flag" (no false positive on a
legitimate bind whose spelling simply isn't in the vocab)."""
import re

from config.app_config import cfg

_CAMEL = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z0-9]+|[A-Z]+")

# unit token → quantity class (dimensional lookup; superset of vocab.unit_quantities, plus the chrome units the
# payload skeletons carry: '°C', 'years', 'min', …). DB row: quantity.unit_classes.
_UNIT_CLASSES_DEFAULT = {
    "v": "voltage", "kv": "voltage",
    "a": "current", "ka": "current",
    "kw": "power", "mw": "power", "w": "power", "kva": "power", "kvar": "power",
    "kwh": "energy", "mwh": "energy", "kvah": "energy", "kvarh": "energy",
    "hz": "frequency",
    "%": "percent", "pct": "percent",
    # an OCCURRENCE-count unit ('count' / 'events' / 'nos') — a count slot takes ONLY a count-quantity source: a
    # percent/power derivation shipped as an EVENT/START count is the c61/c64 pun-bind (Events=4.0 ← loadFactorPct).
    "count": "count", "counts": "count", "events": "count", "nos": "count", "#": "count",
    # a 0-100 INDEX chrome unit ('score' / '/100') — the battery/readiness/health score cells (cards 51/53/57): a
    # score slot takes ONLY a score-quantity source; raw power/voltage dumped into a 'score' leaf is the G-family
    # fabrication and flags via this unit even when the slot path itself is unclassified.
    "score": "score-index", "/100": "score-index",
    "°c": "temperature", "degc": "temperature", "celsius": "temperature", "°f": "temperature",
    "years": "lifetime", "year": "lifetime", "yrs": "lifetime",
    "min": "duration", "mins": "duration", "minutes": "duration", "s": "duration", "sec": "duration",
    "h": "duration", "hr": "duration", "hrs": "duration", "hours": "duration", "ms": "duration", "days": "duration",
    "°": "angle", "deg": "angle",
    # ASSET-DOMAIN units an electrical MFM does NOT sense — a same-family source never exists in a V/A/kW/PF basket,
    # so the slot honest-blanks. rpm = crankshaft tacho (DG); kPa/bar/psi = oil/manifold pressure (DG — also FIXES
    # 'Oil P' kPa mis-reading as temperature/count on card 62).
    "rpm": "engine-speed", "r/min": "engine-speed",
    "kpa": "pressure", "bar": "pressure", "psi": "pressure", "mbar": "pressure",
}

# name token (or ADJACENT-token pair, concatenated) → quantity class. Token-exact — matched against the camelCase/
# underscore-split tokens of a slot path segment / column name / fn name, leaf-most token first, PAIR before single
# (thd+current → current-thd wins over the bare 'current'). Deliberately ABSENT (would false-positive on container
# names / legit stand-ins): load, score, transfer, days, max, min. DB row: quantity.name_classes.
_NAME_CLASSES_DEFAULT = {
    "voltage": "voltage", "volt": "voltage",
    "current": "current", "amps": "current", "ampere": "current",
    # loss-of-life [corpus-replay precision]: 'lolPct' left unclassified fell through to its 'aging.' ANCESTOR segment
    # (aging-factor) and the wall blanked the exactly-right loss_of_life_pct bind (87 ancestor-bleed FPs). The column
    # already classifies lifetime via 'life'; the pair/token below give the SLOT leaf the same class.
    "lol": "lifetime", "lolpct": "lifetime",
    "power": "power", "kw": "power", "kva": "power", "kvar": "power", "watt": "power", "demand": "power",
    "kwh": "energy", "kvah": "energy", "kvarh": "energy", "mwh": "energy", "energy": "energy",
    "consumption": "energy",
    "frequency": "frequency", "hz": "frequency",
    "temperature": "temperature", "temp": "temperature", "hotspot": "temperature", "hotspotc": "temperature",
    "oil": "temperature", "oilc": "temperature", "winding": "temperature", "windingc": "temperature",
    "ambient": "temperature",
    "lifeyears": "lifetime", "lifetime": "lifetime", "life": "lifetime", "years": "lifetime",
    "aging": "aging-factor", "ageing": "aging-factor", "faa": "aging-factor",
    "readiness": "readiness",
    "tapcount": "count", "count": "count", "transfers": "count",
    # occurrence words [c61 'Events' KPI / c64 stats.starts]: an events/starts slot is a COUNT — never a percent/
    # power derivation re-labelled. Plural-only ('event'/'start' singular stay absent: they ride flag-column names
    # like sag_event_active and axisStartMs, where they are NOT the leaf's quantity).
    "events": "count", "starts": "count", "breaches": "count", "trips": "count", "faults": "count",
    "crestfactor": "crest-factor", "crest": "crest-factor",
    "flicker": "flicker", "flickerpst": "flicker", "pst": "flicker", "plt": "flicker",
    "h3": "voltage-harmonic", "h5": "voltage-harmonic", "h7": "voltage-harmonic",
    "h9": "voltage-harmonic", "h11": "voltage-harmonic", "h13": "voltage-harmonic",
    "thdcurrent": "current-thd", "currentthd": "current-thd", "ithd": "current-thd", "thdi": "current-thd",
    "thdvoltage": "voltage-thd", "voltagethd": "voltage-thd", "vthd": "voltage-thd", "thdv": "voltage-thd",
    "deviation": "deviation-spread", "spread": "deviation-spread",
    "unbalance": "unbalance", "imbalance": "unbalance",
    "powerfactor": "power-factor", "pf": "power-factor", "cosphi": "power-factor",
    "loadfactor": "load-factor",
    # PAIR 'load'+'pct' = a load-percentage slot/fn (loadPct / …LoadPctOfRated) — catches raw NEGATIVE kW dumped into a
    # loadPct series (cards 58/76) while loadFactorPct / kpiKwLoadPctOfRated (both classify load-factor via their own
    # pairs) stay compatible. Bare 'load' stays deliberately absent (container false-positives).
    "loadpct": "load-factor",
    "efficiency": "efficiency",                   # efficiencyPct series ← raw power (card 76) flags; no efficiency fn/col exists → honest-blank
    "headroom": "headroom",                       # capacityHeadroom ← loadFactorPct (card 57) flags; a *headroom* fn would classify headroom and pass
    "soc": "battery-charge",                      # state-of-charge is NEVER proxied by an electrical column (card 51 family)
    "slot": "timestamp",                          # a points[*].slot time-label leaf NEVER takes a measured column (card 76); kind=time atoms are exempt upstream
    "angle": "angle", "deg": "angle",
    "minutes": "duration", "hours": "duration", "runtime": "duration", "backuptime": "duration",
    # ── ASSET-DASHBOARD DOMAIN TELEMETRY [cards 51-81] — quantities a single electrical MFM (V/A/kW/PF/energy) CANNOT
    # sense. Each is a NEW hard class with NO measuring column in any electrical basket, so a slot the AI tags with it
    # honest-blanks per the emit rule (no same-qty column → OMIT the field). Leaf-most-first + PAIR-before-single keep
    # every real electrical leaf (inputVoltageV, bypassFrequencyHz, R/Y/B phase) classified on its OWN name FIRST, so
    # these tokens only fire on the genuine domain leaf/container — verified by the full-corpus classification diff.
    # TAP-CHANGER POSITION [transformer tap-rtcc 78-81] — discrete OLTC step (small int); the 'tap' PATH token wins over
    # a "Current position" LABEL (slot_class runs before name_class), killing the current↔"Current position" homonym
    # that bound current_max as the tap position (=−913 regulation.points[*].tap).
    "tap": "tap-position", "tapposition": "tap-position", "oltc": "tap-position", "tapchanger": "tap-position",
    "totap": "tap-position", "fromtap": "tap-position",
    # ENGINE SPEED [DG engine-cooling mech, card 62] — crankshaft rpm; compound tokens only ('speed' bare stays absent).
    "enginespeed": "engine-speed", "speedraw": "engine-speed", "rpm": "engine-speed",
    # OIL / MANIFOLD PRESSURE [DG, card 62 'Oil P'] — the 'oilp' PAIR beats the 'oil'→temperature single (PAIR before
    # single), so oil PRESSURE is no longer mis-classed as oil TEMPERATURE.
    "oilp": "pressure", "oilpressure": "pressure", "pressure": "pressure", "manifold": "pressure",
    # FUEL [DG fuel-efficiency 63-65] — tank level / burn rate / total litres; no MFM fuel source. ('fuelTemp' stays
    # temperature — 'temp' is leaf-most and wins.)
    "fuel": "fuel", "fuellevel": "fuel", "fuelrate": "fuel", "totalfuel": "fuel", "fueltank": "fuel",
    # AUTONOMY / RESERVE [DG snapshot.autonomy 63; UPS 'Autonomy index' 53] — run-time-remaining on current fuel/charge,
    # a fuel/battery-model estimate, no MFM source.
    "autonomy": "autonomy", "autonomyindex": "autonomy",
    # BATTERY / HEALTH COMPOSITE SCORE [UPS 'Overall Battery Score' 51] — a computed 0-100 composite (SoC+temp+bus), not
    # a meter reading. PAIR only (the bare 'score' stays deliberately absent — container FP risk).
    "batteryscore": "readiness", "batteryhealthscore": "readiness", "healthscore": "readiness",
    # SOURCE-TRANSFER ACTIVITY [UPS source-transfer 55] — days-since / count of static-switch transfers; a transfer-
    # switch event the MFM does not log (FIVE WALLS #5). ('transfers' plural already → count.)
    "transferdays": "count", "lasttransfer": "count",
}

# dimension-only classes too generic to flag: an unclassified-by-name '%' column could be ANY percent-semantic —
# cautious compatibility, never a blank on dimension alone. DB row: quantity.weak_classes.
_WEAK_CLASSES_DEFAULT = ["percent"]

# NAME-LEVEL SEMANTIC FAMILIES [card 65: kpis[0] 'Efficiency' = 5.3 ← fn loadFactorPct]: a SAME-DIMENSION pun slips
# the dimensional wall because 'percent' is WEAK — but a slot whose NAME (label / metric / slot leaf) says
# efficiency / SFC / consumption / fuel makes a SEMANTIC claim inside that dimension. Such a slot binds ONLY a
# source (fn / column) whose OWN name belongs to the SAME family — or whose quantity CLASS the family explicitly
# licenses ('Consumption 412 kWh' ← active_energy_import_kwh: energy/power classes ARE consumption). DB row:
# quantity.semantic_families — {family: {"markers": [...], "classes": [...]}}. Markers match TOKEN-EXACT (a
# multi-word marker matches an ADJACENT token run: 'specific energy consumption' ↔ specificEnergyConsumption),
# never substring. A slot claiming NO family never flags here (no false positive on plain value slots).
_SEMANTIC_FAMILIES_DEFAULT = {
    "efficiency": {"markers": ["efficiency"], "classes": ["efficiency"]},
    "specific-consumption": {"markers": ["sfc", "specific consumption", "specific fuel consumption",
                                         "specific energy consumption"], "classes": []},
    "consumption": {"markers": ["consumption", "consumed"], "classes": ["energy", "power"]},
    "fuel": {"markers": ["fuel"], "classes": []},
}

# NAME-LEVEL SOURCE ROLES [card 59: composite.points[*].bypassVoltageV / bypassFrequencyHz ← voltage_avg / frequency_hz]:
# a SAME-QUANTITY, DIFFERENT-ROLE smear that slips BOTH the dimensional quantity wall (voltage↔voltage, freq↔freq are
# compatible so `compatible` returns True) AND the reuse-smear wall (the shared bind classifies, so rule (ii) defers to
# the quantity wall which then passes it). A UPS presents several PHYSICALLY DISTINCT sensing points of the SAME
# electrical quantity — INPUT/line, OUTPUT/load, BYPASS/static-switch, BATTERY, RECTIFIER — and this gic_* meter senses
# only the INPUT/line (voltage_avg / frequency_hz ARE the input reading; the schema has NO bypass column). A slot whose
# NAME claims a DEDICATED-SENSING role (bypass / output / battery / rectifier) must bind a source whose OWN name carries
# that SAME role; binding it the meter's plain input/line reading presents the input AS the bypass — a fabrication (the
# card's own data_note even says bypass is not measured by this meter). The RIGHT outcome: the bypass leaf HONEST-BLANKS.
# DB row: quantity.source_roles — {role: {"markers":[...], "dedicated": true}}. `markers` = the role tokens a slot/source
# NAME carries (token-EXACT, leaf-most first — same discipline as the class vocab). `dedicated`:true = this role has its
# OWN sensor: a slot claiming it binds ONLY a source that ALSO claims it; a same-quantity source claiming a DIFFERENT
# dedicated role, or NO role at all (the plain meter reading), is a role smear and honest-blanks. A NON-dedicated role
# (input/line/mains — the meter's plain reading) NEVER flags: input* slots legitimately bind the bare voltage_avg /
# frequency_hz. A slot claiming NO role never flags (no false positive on plain value slots).
# SCOPE [minimal, grounded]: seeded with the ONE verified defect — `bypass` (the gic_* UPS meter has NO bypass column,
# confirmed against information_schema; voltage_avg / frequency_hz ARE the input reading). Additional dedicated-sensing
# roles (output / battery / rectifier) are NOT seeded here — those punned binds are already caught by the score-index /
# quantity walls, and adding them would re-classify (not mis-render, but re-word) those already-correct blanks. Add a
# role row only when a NEW same-quantity-different-role smear is found that no other wall catches.
_SOURCE_ROLES_DEFAULT = {
    "bypass": {"markers": ["bypass"], "dedicated": True},
    "input": {"markers": ["input", "line", "mains"], "dedicated": False},
}

# TIME-AXIS LABEL leaf tokens [card 59 secondary: composite.points[*].label ← active_power_total_kw = negative kW
# rendered AS x-axis time labels]: the per-point `label` / `slot` leaf of a time SERIES is the time-axis tick label —
# it is filled from the card's OWN bucket timestamps (kind=time), NEVER from a measured column. A raw/bucketed field
# binding a MEASURED column into such a leaf ships the reading as a time label (the negative-kW-as-time defect). A
# kind=time atom (the correct emission) carries no column and is exempt by construction. Token-exact, leaf-most only.
# DB row: quantity.time_axis_label_tokens.
_TIME_AXIS_LABEL_TOKENS_DEFAULT = ["label", "slot", "time", "ts", "tick", "axislabel", "timestamp", "bucket"]

# HARD DIMENSIONAL classes — the absolute electrical/thermal dimensions a WEAK (ratio-only) side can never stand in
# for: a '%'-declared slot fed a kW column ships raw kilowatts labelled '%' (card 42: −197.4 kW anomalies under
# unit='%'), and a kW slot fed a bare-'%' column is the same fabrication mirrored. A weak side stays compatible with
# every ratio-like class (load-factor / unbalance / thd / efficiency / score …). DB row: quantity.dimensional_classes.
_DIMENSIONAL_CLASSES_DEFAULT = ["voltage", "current", "power", "energy", "frequency", "temperature"]

# DIRECTIONAL (slot ← source) compatibility grants [corpus-replay precision]: a STATISTIC-KIND class may legitimately
# fill a slot of the base dimension it is a statistic OF — current_max_spread ('spread' → deviation-spread) into the
# card-46 'Max Spread (A)' metrics cell is a REAL amps-dimensioned spread stat, not a re-purposed number (91 corpus
# FPs: the sibling unit 'A' outranked the spread label in slot evidence). ORDERED pairs [slot_class, source_class] —
# the REVERSE stays incompatible (a deviation SLOT fed a voltage source/band is still the maxDeviation ←
# voltageStatutoryBand fabrication), and crest-factor/flicker ← deviation-spread stays a catch. DB row:
# quantity.compatible_slot_source_pairs.
_COMPATIBLE_SLOT_SOURCE_PAIRS_DEFAULT = [["current", "deviation-spread"], ["voltage", "deviation-spread"]]

# STRUCTURAL const name tokens [corpus-replay precision]: a kind=const whose metric / slot-leaf names a pure
# DISPLAY/FRAME knob (formatter decimals, a selected-sample index, an area/dim opacity, a layout code, a windowDays
# span) states NO measurement — blanking it broke formatting/selection chrome without preventing any fabrication
# (~450 corpus FPs: decimals=0, selectedSampleIndex=1, areaOpacity=0.0, layout=28, windowDays=30). Token-exact /
# adjacent-pair matched, same discipline as the class vocab — a QUANTITY-named const (131 A, 0.0 kW, 1461 kWh)
# never matches and stays policed. DB row: quantity.structural_const_tokens.
_STRUCTURAL_CONST_TOKENS_DEFAULT = ["decimals", "opacity", "index", "layout", "windowdays"]


def _unit_map():
    return {str(k).replace(" ", "").lower(): str(v) for k, v in
            (cfg("quantity.unit_classes", _UNIT_CLASSES_DEFAULT) or {}).items()}


def _name_map():
    return {str(k).replace(" ", "").lower(): str(v) for k, v in
            (cfg("quantity.name_classes", _NAME_CLASSES_DEFAULT) or {}).items()}


def _weak():
    return {str(c).lower() for c in (cfg("quantity.weak_classes", _WEAK_CLASSES_DEFAULT) or [])}


def _dimensional():
    return {str(c).lower() for c in (cfg("quantity.dimensional_classes", _DIMENSIONAL_CLASSES_DEFAULT) or [])}


def _compatible_pairs():
    """ORDERED (slot_class, source_class) grants from the DB row (code-default mirror)."""
    raw = cfg("quantity.compatible_slot_source_pairs", _COMPATIBLE_SLOT_SOURCE_PAIRS_DEFAULT) or []
    return {(str(p[0]).lower(), str(p[1]).lower()) for p in raw
            if isinstance(p, (list, tuple)) and len(p) == 2}


def _structural_const_tokens():
    return {str(t).replace(" ", "").lower() for t in
            (cfg("quantity.structural_const_tokens", _STRUCTURAL_CONST_TOKENS_DEFAULT) or [])}


def structural_const_name(field):
    """True when a kind=const field's metric / slot-leaf names a pure DISPLAY/FRAME knob (quantity.structural_const_
    tokens: decimals / opacity / index / layout / windowDays) — such a literal states NO measurement, so the
    const-source guard leaves it alone (blanking it broke formatter/selection chrome without preventing fabrication).
    Token-exact / adjacent-pair matching (the class-vocab discipline — never substring)."""
    if not isinstance(field, dict):
        return False
    toks_set = _structural_const_tokens()
    if not toks_set:
        return False
    for name in (field.get("metric"), _slot_leaf(field.get("slot"))):
        toks = _tokens(name)
        for i, t in enumerate(toks):
            if t in toks_set or (i > 0 and (toks[i - 1] + t) in toks_set):
                return True
    return False


def _generic_tokens():
    """Structural container / bare-value path tokens that carry NO quantity semantic — REUSES the existing DB-driven
    set (config.metrics GENERIC_SLOT_TOKENS row metrics.generic_slot_tokens) so there is exactly ONE such vocabulary."""
    try:
        from config.metrics import GENERIC_SLOT_TOKENS
        return set(GENERIC_SLOT_TOKENS)
    except Exception:
        return {"value", "val", "amount", "data", "vm", "kpis", "snapshot", "views", "view", "series",
                "points", "stats", "legend", "label", "pct"}


def _tokens(text):
    return [p.lower() for p in _CAMEL.findall(str(text or "")) if p]


def _classify_tokens(toks):
    """Leaf-most token first; the ADJACENT PAIR (predecessor+token) beats the single token (thd_current → current-thd,
    never bare 'current'); generic/digit tokens are skipped. None when nothing classifies."""
    nm, generic = _name_map(), _generic_tokens()
    for i in range(len(toks) - 1, -1, -1):
        t = toks[i]
        if i > 0 and (toks[i - 1] + t) in nm:
            return nm[toks[i - 1] + t]
        if t in generic or t.isdigit():
            continue
        if t in nm:
            return nm[t]
    return None


def unit_class(unit):
    """The quantity class a unit string names ('°C' → temperature, 'kW' → power), or None."""
    return _unit_map().get(str(unit or "").replace(" ", "").lower()) or None


def name_class(name):
    """The quantity class of a FLAT name (a basket column, a derivation fn, a metric label), or None."""
    if not name:
        return None
    return _classify_tokens(_tokens(name))


def slot_class(slot):
    """The quantity class a SLOT PATH's own tokens name — per SEGMENT, leaf-most segment first (so the leaf's
    'hotspotC' beats an ancestor container), digits/[*] skipped. None when no segment classifies (a generic
    'chart.series[0].values' path never flags)."""
    segs = [s for s in re.findall(r"[^.\[\]]+", str(slot or "")) if s and not s.isdigit() and s != "*"]
    for seg in reversed(segs):
        c = _classify_tokens(_tokens(seg))
        if c:
            return c
    return None


def column_class(entry):
    """The quantity class of a BASKET COLUMN entry ({column, unit, …}) — its self-describing NAME first (specific:
    thd_current_r_pct → current-thd), else its describe unit (dimensional: '%' → percent). None = unclassified."""
    if not isinstance(entry, dict):
        entry = {"column": entry}
    return name_class(entry.get("column")) or unit_class(entry.get("unit"))


def compatible(slot_cls, source_cls):
    """False on a confident cross-quantity bind: both sides classified and different, and either (a) NEITHER side is
    WEAK (dimension-only), or (b) one side is weak but the OTHER names a HARD DIMENSIONAL class — a ratio ('%') can
    never BE kilowatts/volts/°C, in either direction (the card-42 family: six '%'-declared slots fed raw signed
    active_power_total_kw shipped −197 kW as percentages). Weak vs any ratio-like class stays compatible (cautious:
    an unclassified-by-name '%' column could be ANY percent-semantic). None on either side = unknown = compatible
    (no false positive on unfamiliar spellings). An ORDERED (slot, source) grant in quantity.compatible_slot_source_
    pairs is compatible by decree (a statistic-kind source filling a slot of its base dimension: an amps-cell ←
    deviation-spread stat) — the reverse direction is NOT granted."""
    if not slot_cls or not source_cls or slot_cls == source_cls:
        return True
    if (slot_cls.lower(), source_cls.lower()) in _compatible_pairs():
        return True
    w = _weak()
    s_weak, c_weak = slot_cls.lower() in w, source_cls.lower() in w
    if s_weak and c_weak:
        return True
    if s_weak or c_weak:
        other = source_cls if s_weak else slot_cls
        return other.lower() not in _dimensional()             # '%' ↔ kW/V/°C is a dimension breach, not a stand-in
    return False


def _families_cfg():
    """{family: ([marker token tuples], {licensed classes})} from the DB row (code-default mirror). Tolerates a bare
    marker-list row value ({family: [markers]})."""
    raw = cfg("quantity.semantic_families", _SEMANTIC_FAMILIES_DEFAULT) or {}
    out = {}
    for fam, spec in raw.items():
        if isinstance(spec, dict):
            markers, classes = spec.get("markers") or [], spec.get("classes") or []
        else:
            markers, classes = list(spec or []), []
        seqs = [tuple(_tokens(m)) for m in markers]
        out[str(fam)] = ([s for s in seqs if s], {str(c).lower() for c in classes})
    return out


def _marker_hit(toks, seq):
    n = len(seq)
    return n > 0 and any(tuple(toks[i:i + n]) == seq for i in range(len(toks) - n + 1))


def semantic_families(*names):
    """The set of NAME-LEVEL semantic families ANY of `names` claims (token-exact marker match; a multi-word marker
    matches an adjacent token run). Empty set = no claim (callers never flag)."""
    fams = set()
    fam_map = _families_cfg()
    for name in names:
        toks = _tokens(name)
        if not toks:
            continue
        for fam, (seqs, _cls) in fam_map.items():
            if any(_marker_hit(toks, s) for s in seqs):
                fams.add(fam)
    return fams


def semantic_family_mismatch(slot_names, source_name, source_cls=None):
    """(True, [families]) on a NAME-LEVEL semantic-family breach: the SLOT side (any of `slot_names`: slot path,
    metric, sibling label) claims ≥1 family while the SOURCE name claims NONE of them and its quantity class is not
    family-licensed — the card-65 'Efficiency' ← loadFactorPct same-dimension pun. (False, None) when the slot claims
    no family, the families intersect, or the source class is licensed — unclaimed/unknown never flags."""
    fams = semantic_families(*(slot_names or ()))
    if not fams:
        return False, None
    if fams & semantic_families(source_name):
        return False, None
    fam_map = _families_cfg()
    licensed = set()
    for f in fams:
        licensed |= fam_map.get(f, ((), set()))[1]
    if source_cls and str(source_cls).lower() in licensed:
        return False, None
    return True, sorted(fams)


def _roles_cfg():
    """{role: ([marker token tuples], dedicated:bool)} from the DB row (code-default mirror). Tolerates a bare
    marker-list row value ({role: [markers]} → dedicated defaults True)."""
    raw = cfg("quantity.source_roles", _SOURCE_ROLES_DEFAULT) or {}
    out = {}
    for role, spec in raw.items():
        if isinstance(spec, dict):
            markers = spec.get("markers") or []
            dedicated = bool(spec.get("dedicated", True))
        else:
            markers, dedicated = list(spec or []), True
        seqs = [tuple(_tokens(m)) for m in markers]
        out[str(role)] = ([s for s in seqs if s], dedicated)
    return out


def source_roles(*names):
    """The set of NAME-LEVEL source roles ANY of `names` claims (token-exact marker match; a multi-word marker matches
    an adjacent token run). Empty set = no role claim (callers never flag)."""
    roles = set()
    role_map = _roles_cfg()
    for name in names:
        toks = _tokens(name)
        if not toks:
            continue
        for role, (seqs, _ded) in role_map.items():
            if any(_marker_hit(toks, s) for s in seqs):
                roles.add(role)
    return roles


def source_role_mismatch(slot_names, source_name):
    """(True, [roles]) on a NAME-LEVEL SOURCE-ROLE breach: the SLOT side (any of `slot_names`: slot path, metric,
    sibling label) claims ≥1 DEDICATED-SENSING role (bypass / output / battery / rectifier — a physically distinct
    sensing point) while the SOURCE name claims NONE of the slot's roles — the card-59 bypassVoltageV ← voltage_avg
    same-quantity role smear (the input/line reading presented AS the bypass reading; this meter has NO bypass sensor).
    (False, None) when the slot claims no dedicated role, or the source shares one of the slot's roles (bypassVoltage ←
    a real bypass_voltage column passes). A NON-dedicated role (input/line/mains — the meter's plain reading) never
    flags: an input* slot legitimately binds the bare voltage_avg. Unclaimed/unknown never flags — no false positive on
    plain value slots or unfamiliar spellings."""
    slot_roles = source_roles(*(slot_names or ()))
    role_map = _roles_cfg()
    dedicated = {r for r in slot_roles if role_map.get(r, ((), False))[1]}
    if not dedicated:
        return False, None
    if dedicated & source_roles(source_name):
        return False, None
    return True, sorted(dedicated)


def _time_axis_label_tokens():
    return {str(t).replace(" ", "").lower() for t in
            (cfg("quantity.time_axis_label_tokens", _TIME_AXIS_LABEL_TOKENS_DEFAULT) or [])}


def is_time_axis_label_slot(slot):
    """True when a slot's LEAF token is a series time-axis label (label / slot / time / ts / tick — DB row
    quantity.time_axis_label_tokens) AND the slot is a per-element series path ([*] / an indexed points list): such a
    leaf is filled from the card's own bucket timestamps (kind=time), never a measured column. Leaf-token-exact so a
    'label' that is NOT a per-point series leaf (a legend/badge label) never matches — a plain scalar label is not a
    time axis. [card 59 secondary: composite.points[*].label ← active_power_total_kw]."""
    segs = [s for s in re.findall(r"[^.\[\]]+", str(slot or "")) if s and s != "*"]
    if not segs:
        return False
    leaf = segs[-1].lower()
    if leaf not in _time_axis_label_tokens():
        return False
    # only a per-ELEMENT series leaf (wildcard/indexed list path) is a time axis — a bare scalar label is not
    return "[*]" in str(slot) or any(s.isdigit() for s in re.findall(r"[^.\[\]]+", str(slot or "")))


def slot_quantity(slot, ctx=None):
    """The slot's EXPECTED quantity for the emit CONTEXT (slot-catalog line): the payload's own sibling unit chrome
    first (VERBATIM skeleton truth: '°C' → temperature), then the slot path's name tokens, then the sibling label.
    None = unclassified (the line shows no expectation; the gate never flags it)."""
    c = ctx or {}
    return unit_class(c.get("unit")) or slot_class(slot) or name_class(c.get("label"))


# ── const-source resolution (the 131A / 1000kVA class-killer) ─────────────────────────────────────────────────────
_CONST_NAMESPACE = "consts."     # the sanctioned app_config home for site-approved literal thresholds/bands/axes


def _const_rows():
    """{normalized row name: (key, parsed numeric value)} for every app_config `consts.*` row — the ONE sanctioned
    namespace for literal data-slot constants (a row elsewhere never accidentally licenses a const). Empty on DB
    outage (fail-closed for consts: an unresolvable const blanks, never fabricates)."""
    try:
        from config.app_config import _load
        rows = _load()
    except Exception:
        return {}
    out = {}
    for key, (val, dt) in rows.items():
        if not str(key).startswith(_CONST_NAMESPACE):
            continue
        name = re.sub(r"[^a-z0-9]+", "", str(key)[len(_CONST_NAMESPACE):].lower())
        parsed = _parse_numeric(val, dt)
        if name and parsed is not None:
            out[name] = (key, parsed)
    return out


def _parse_numeric(val, dt):
    try:
        if dt == "json":
            import json
            v = json.loads(val)
            if isinstance(v, list) and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v):
                return [float(x) for x in v]
            return None
        return float(val)
    except Exception:
        return None


def _norm(name):
    return re.sub(r"[^a-z0-9]+", "", str(name or "").lower())


def _num_eq(a, b):
    """Tolerant numeric equality (int/float spellings, decimal round-trip noise) — never a magnitude change."""
    import math
    try:
        return math.isclose(float(a), float(b), rel_tol=1e-9, abs_tol=1e-9)
    except (TypeError, ValueError):
        return False


def _values_equal(emitted, row_value):
    try:
        if isinstance(row_value, list):
            if isinstance(emitted, list):
                return len(emitted) == len(row_value) and all(_num_eq(a, b) for a, b in zip(emitted, row_value))
            # a SCALAR citing one element of a list row (a [min,max] band row cited as expectedMin / expectedMax
            # separately) is the same site-approved literal — equality was too strict, not the licence
            return not isinstance(emitted, bool) and any(_num_eq(emitted, b) for b in row_value)
        return _num_eq(emitted, row_value)
    except (TypeError, ValueError):
        return False


def numericish(v):
    """True for the values the const-source guard polices: a number or a list of numbers (booleans/strings/None are
    text/flag chrome, policed elsewhere)."""
    if isinstance(v, bool):
        return False
    if isinstance(v, (int, float)):
        return True
    return isinstance(v, list) and bool(v) \
        and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v)


def _slot_leaf(slot):
    toks = re.findall(r"[^.\[\]]+", str(slot or ""))
    toks = [t for t in toks if not t.isdigit() and t != "*"]
    return toks[-1] if toks else ""


def const_source(field):
    """Resolve a kind=const NUMERIC field to its REAL DB source, mirroring exactly what the executor will do:
      ("nameplate", rating_key)  — the slot/metric is a nameplate rating per config.nameplate_slot_map (the SAME
                                   probes fill.py runs), so the executor substitutes the asset's REAL rating or
                                   honest-blanks; the baked value is only a shape placeholder;
      ("app_config", row_key)    — an app_config `consts.<name>` row matches the field's metric / slot leaf name AND
                                   the emitted value EQUALS the row's (the row is the citation);
      None                       — no real source: the value is a Storybook seed / invented figure (the 131 A /
                                   1000 kVA class) and the gate blanks the leaf."""
    if not isinstance(field, dict):
        return None
    try:
        from config.nameplate_slot_map import rating_key_for
        rk = rating_key_for(field.get("slot")) or rating_key_for(field.get("metric"))
    except Exception:
        rk = None
    if rk:
        return ("nameplate", rk)
    rows = _const_rows()
    for name in (_norm(field.get("metric")), _norm(_slot_leaf(field.get("slot")))):
        hit = rows.get(name) if name else None
        if hit and _values_equal(field.get("value"), hit[1]):
            return ("app_config", hit[0])
    return None
