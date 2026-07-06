"""layer2/resolve/column_override.py — SAFE per-field column binding: snap each field to the basket column for its
metric ONLY when that metric is unique on the card AND the unit/quantity is compatible; drop a hallucinated column
(not in basket, not const/$ctx). The unit-guard [DID-06] stops a mislabelled metric snapping to a semantically-wrong
real column (e.g. an apparent-kVA field snapping onto the sole 'power'-tagged active-kW column). [PROMPTS §L2 gate 3]

SLOT-QUANTITY GUARD [2026-07-03 PCC-4 defect E]: the slot KEY names its own display quantity (`…Kw` → kW, `…Kwh` →
kWh, `…Pct` → %) — the KPI-QUANTITY rule of the data_instructions prompt. An emission that binds a column of a
DIFFERENT known quantity into such a slot WITHOUT declaring the proxy (empty `data_note`) rendered a kWh counter
delta as '1,820,542 kW'. The guard drops that binding to the frame path (column=None → the leaf honest-blanks) —
per-leaf honest-degrade, never a card-level conformance failure. A DECLARED proxy (non-empty data_note) passes ONLY
when the emission ALSO carried the mandated display morph (an APPLIED metadata morph inside the slot's own parent
block — e.g. `…kpis.unit` for `…kpis.sourceInputKw`); a declared-but-unmorphed proxy still renders the wrong reading
under the designed unit, so it is treated as undeclared and honest-blanked."""


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


_SLOT_QTY_SUFFIXES = ("kvarh", "kvah", "kwh", "kvar", "kva", "kw", "pct")


def _slot_quantity(slot):
    """The display quantity a slot KEY itself names (…Kw → 'kw', …Kwh → 'kwh', …Pct → '%'), or None (no claim —
    unsuffixed keys carry no unit claim, so no guard)."""
    last = str(slot or "").split(".")[-1].split("[")[0].strip().lower()
    for suf in _SLOT_QTY_SUFFIXES:
        if last.endswith(suf) and last != suf or last == suf:
            return "%" if suf == "pct" else suf
    return None


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


def _display_morphed(slot, applied_morphs):
    """Did the emission morph any metadata leaf in the slot's OWN parent block (the mandated proxy unit/caption
    morph)? Path arithmetic only — no key names, no card knowledge."""
    parent = ".".join(str(slot or "").split(".")[:-1])
    if not parent:
        return False
    return any(str(mp) == parent or str(mp).startswith(parent + ".") or str(mp).startswith(parent + "[")
               for mp in (applied_morphs or []))


def apply(data_instructions, basket, data_note=None, applied_morphs=None, is_group_card=False):
    """Return (data_instructions, notes[]). Mutates fields[].column to a real basket column where safe. `data_note`
    (the emission's own degradation note) + `applied_morphs` (the APPLIED metadata morph paths) mark a DECLARED,
    display-morphed proxy — the slot-quantity guard stands down only for that. `is_group_card` gates the $ctx repair
    (source=$ctx is legal ONLY on a group card).

    `notes` is NON-GATING TELEMETRY [silent-normalization defect]: every repair this normalizer performs (mislabelled
    const reclass, slot-quantity blank, metric snap, hallucinated-column drop) used to be completely invisible — an
    emission that bound four invented columns shipped conforms=True with zero record. Each normalization now appends a
    note; build.py carries them in data_instructions['_normalized'] (telemetry for sweeps / the prompt-steer loop),
    NEVER in `failures` and NEVER affecting conforms — per-leaf degradation, verdicts are telemetry."""
    by_metric, real, unit_by_col = _basket_index(basket)
    notes = []
    proxy_declared = bool(str(data_note or "").strip())
    for f in (data_instructions.get("fields") or []):
        src = f.get("source")
        # MISLABELLED-CONST REPAIR [thermal-legend defect]: a truly literal field is source=='const' WITH a baked
        # `value`. When the AI stamps kind=='const' on a field it ALSO marked live/frame/test-db (a data binding — it
        # carries a metric, agg, no value), that is not a literal: it is an intended live/frame leaf mis-tagged as
        # const. Reclassify it to the FRAME honest-blank path (column=None → the leaf renders blank, per-leaf degrade)
        # so a missing column blanks THAT one leaf instead of tripping the card-level 'kind=const without a value'
        # gate. A real literal (source=='const' or a present value) is untouched. Generic — no card/slot vocab.
        if f.get("kind") == "const" and src in ("live", "frame", "test-db") and f.get("value") is None:
            f["kind"] = "raw"
            src = f["source"] = "frame"
            notes.append(f"slot {f.get('slot')!r}: mislabelled const (source={src}, no value) reclassified to frame")
        # $ctx-ON-STANDALONE REPAIR [c73 false-blank]: source=$ctx is legal ONLY on a GROUP card (it reads the page's
        # shared buffer). On a STANDALONE card the AI mis-emitted it — but if the field NAMES A REAL BASKET COLUMN it IS
        # a live bind on the resolved asset, so reclassify $ctx→live and let the executor fill the measurable series (the
        # DG power trend rendered EMPTY because a standalone card cannot fill $ctx server-side). A $ctx field naming no
        # real column drops to the frame/honest-blank path. Generic, no card ids; a real GROUP card keeps $ctx untouched.
        if src == "$ctx" and not is_group_card:
            _c = f.get("column")
            if _c and _c in real and f.get("kind") != "const":
                src = f["source"] = "live"
                notes.append(f"slot {f.get('slot')!r}: source=$ctx on a standalone card reclassified to live "
                             f"(real column {_c!r}) — measurable leaf fills instead of a $ctx false-blank")
            else:
                f["column"], f["source"] = None, "frame"
                notes.append(f"slot {f.get('slot')!r}: source=$ctx on a standalone card names no real column → "
                             f"frame/honest-blank")
                continue
        if f.get("kind") == "const" or src == "$ctx" or src == "const":
            continue                                   # const baked / shared-buffer projection: no column needed
        col, metric = f.get("column"), f.get("metric")
        # SLOT-QUANTITY GUARD — a unit-crossing binding (a kWh counter bound into a `…Kw` slot) honest-blanks the
        # leaf unless it is a DECLARED proxy WHOSE display metadata was morphed [PCC-4 defect E].
        if col and col in real and f.get("kind") not in ("derived", "time"):
            sq = _slot_quantity(f.get("slot"))
            cq = _unit_of(unit_by_col.get(col)) or _col_unit(col)
            if sq is not None and cq is not None and sq != cq \
                    and not (proxy_declared and _display_morphed(f.get("slot"), applied_morphs)):
                f["column"] = None
                f["source"] = "frame"                  # undeclared/unmorphed different-quantity proxy → honest-blank
                notes.append(f"slot {f.get('slot')!r}: unit-crossing bind {col!r} ({cq}) into a {sq} slot blocked "
                             f"(undeclared/unmorphed proxy) — leaf honest-blanks")
                continue
        cols_for_metric = by_metric.get(metric, [])
        if len(cols_for_metric) == 1 and col != cols_for_metric[0]:
            # SAFE snap (metric unique on the card) — GUARDED by unit compatibility [DID-06]. A KNOWN unit mismatch
            # (e.g. the field declared kVA but the sole metric column is _kw) does NOT snap: drop to the frame path
            # rather than substitute a wrong-quantity real column.
            target = cols_for_metric[0]
            if _units_compatible(f.get("unit"), target, unit_by_col):
                f["column"] = target
                notes.append(f"slot {f.get('slot')!r}: column {col!r} snapped to {target!r} (unique metric {metric!r})")
            elif col and col not in real:
                f["column"] = None
                f["source"] = "frame"                  # unit mismatch + hallucinated column → frame-filled, honest-degrade
                notes.append(f"slot {f.get('slot')!r}: hallucinated column {col!r} dropped (unit-incompatible with "
                             f"{target!r}) — frame/honest-blank")
        elif col and col not in real:
            # DROP the hallucinated column (names no real column, can't be snapped) and mark the field FRAME-filled:
            # the frontend fills it from the live frame's fan-out / list structure (a Sankey's per-feeder
            # id/source/target/value/sourceInputKw come from frame.outgoings, not a meter column). This is the gate's
            # stated "drop a hallucinated column" intent — honest-degrade, not a hard conformance failure.
            f["column"] = None
            f["source"] = "frame"
            notes.append(f"slot {f.get('slot')!r}: hallucinated column {col!r} dropped (not in basket) — "
                         f"frame/honest-blank")
    return data_instructions, notes
