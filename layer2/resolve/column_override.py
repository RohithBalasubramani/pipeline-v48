"""layer2/resolve/column_override.py — SAFE per-field column binding: snap each field to the basket column for its
metric ONLY when that metric is unique on the card AND the unit/quantity is compatible; drop a hallucinated column
(not in basket, not const/$ctx). The unit-guard [DID-06] stops a mislabelled metric snapping to a semantically-wrong
real column (e.g. an apparent-kVA field snapping onto the sole 'power'-tagged active-kW column). [PROMPTS §L2 gate 3]"""


def _unit_of(u):
    """Normalize a declared/column unit to a comparison key. '' / None → None (dimensionless / unknown: no guard).
    kW/kVA/kVAr/kWh/kVAh/kVArh/V/A/%/Hz are compared case-insensitively. A trailing-suffix column name (…_kva) also
    resolves — the basket already carries the parsed unit, but the AI may declare either form."""
    if not u:
        return None
    s = str(u).strip().lower()
    for key in ("kvarh", "kvah", "kwh", "kvar", "kva", "kw", "hz"):
        if s.endswith(key) or s == key:
            return key
    if s in ("v", "volt", "volts"):
        return "v"
    if s in ("a", "amp", "amps", "ampere", "amperes"):
        return "a"
    if s in ("%", "pct", "percent"):
        return "%"
    return s


def _col_unit(col):
    """The unit implied by a real column NAME suffix (mirrors layer1b.basket.describe.unit, kept dependency-free)."""
    c = (col or "").lower()
    for suf, key in (("_kwh", "kwh"), ("_kvah", "kvah"), ("_kvarh", "kvarh"),
                     ("_kw", "kw"), ("_kva", "kva"), ("_kvar", "kvar"), ("_pct", "%"), ("_hz", "hz")):
        if c.endswith(suf):
            return key
    if c.startswith("voltage_"):
        return "v"
    if c.startswith("current_"):
        return "a"
    if c.startswith("thd_"):
        return "%"
    return None


def _units_compatible(declared_unit, target_col, basket_unit_by_col):
    """True iff the AI's declared unit is compatible with the target column's unit (or either is unknown → no guard,
    permissive). A KNOWN mismatch (kVA declared vs a _kw column) blocks the snap."""
    d = _unit_of(declared_unit)
    t = _unit_of(basket_unit_by_col.get(target_col)) or _col_unit(target_col)
    if d is None or t is None:
        return True                                    # dimensionless / unknown on either side → don't over-block
    return d == t


def _basket_index(basket):
    by_metric, real, unit_by_col = {}, set(), {}
    for c in (basket.get("columns") or []):
        col = c.get("column")
        if not col:
            continue
        real.add(col)
        unit_by_col[col] = c.get("unit")
        m = c.get("metric")
        if m:
            by_metric.setdefault(m, []).append(col)
    return by_metric, real, unit_by_col


def apply(data_instructions, basket):
    """Return (data_instructions, issues[]). Mutates fields[].column to a real basket column where safe."""
    by_metric, real, unit_by_col = _basket_index(basket)
    issues = []
    for f in (data_instructions.get("fields") or []):
        src = f.get("source")
        if f.get("kind") == "const" or src == "$ctx" or src == "const":
            continue                                   # const baked / shared-buffer projection: no column needed
        col, metric = f.get("column"), f.get("metric")
        cols_for_metric = by_metric.get(metric, [])
        if len(cols_for_metric) == 1 and col != cols_for_metric[0]:
            # SAFE snap (metric unique on the card) — GUARDED by unit compatibility [DID-06]. A KNOWN unit mismatch
            # (e.g. the field declared kVA but the sole metric column is _kw) does NOT snap: drop to the frame path
            # rather than substitute a wrong-quantity real column.
            target = cols_for_metric[0]
            if _units_compatible(f.get("unit"), target, unit_by_col):
                f["column"] = target
            elif col and col not in real:
                f["column"] = None
                f["source"] = "frame"                  # unit mismatch + hallucinated column → frame-filled, honest-degrade
        elif col and col not in real:
            # DROP the hallucinated column (names no real column, can't be snapped) and mark the field FRAME-filled:
            # the frontend fills it from the live frame's fan-out / list structure (a Sankey's per-feeder
            # id/source/target/value/sourceInputKw come from frame.outgoings, not a meter column). This is the gate's
            # stated "drop a hallucinated column" intent — honest-degrade, not a hard conformance failure.
            f["column"] = None
            f["source"] = "frame"
    return data_instructions, issues
