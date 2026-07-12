"""layer2/gates/walls.py — the per-field HONEST-BLANK wall predicates (SEAM 2): each `(True, reason)` rule is an
independent pure function (quantity mismatch, const-without-source, axis direction/source, expectation direct-bind,
topology boundary proxy, time-axis label bind, live-claim-without-source). enforce_honest_blank (honest_blank.py)
sequences them. Every quantity import stays function-local (as in the original module)."""
from config.app_config import cfg
from layer2.gates.basket import _bindable, _col_issue, _nameplate_missing   # noqa: F401  (walls read the basket predicates)

# ── HONEST-BLANK enforcement (SEAM 2) ─────────────────────────────────────────────────────────────────────────────
# A data slot whose OWN quantity has NO backing column in the asset basket must render an HONEST BLANK, never a proxy
# fn/column of another quantity, a constant, or a value reused from a sibling slot (mandate: DATA only from neuract,
# per-LEAF honest degradation). The prompt forbids it; this deterministic pass ENFORCES it by dropping (blanking) the
# offending field so a leaf that cannot be measured stays empty instead of shipping a fabricated number. Data-driven
# from the basket + the emit's own field shape — NO card/slot ids, NO hardcoded fn/column vocab. Reported as telemetry
# (di._honest_blanked), NOT a card-blocking gate failure (a self-healed leaf is a per-leaf degradation, not a defect).
import re as _re

# A field is a SERIES/AXIS ANCHOR when it (or the group it shares a binding with) is a time-series or that series' own
# derived summary (legend latest-value / kpi / axis min/max). Such a co-bind is ONE quantity across related slots and is
# NEVER the reuse defect — only ≥2 DISTINCT-quantity SCALAR cells sharing one binding, with NO series anchor, are.
def _is_series_anchor(f):
    slot = str(f.get("slot") or "")
    if f.get("kind") == "bucketed" or f.get("role") in ("series", "line"):
        return True
    if slot.endswith(".values") or "[*]" in slot:
        return True
    if _re.search(r"(?:^|\.)(?:[A-Za-z0-9]*Axis)?\.?(?:max|min)$", slot):   # …Axis.max / .max / .min = series bound
        return True
    return False


def _blankable_field(f, real, failed, nameplate_missing):
    """True + reason when a field must honest-blank: its OWN measured column / derived base-column is HALLUCINATED
    (absent from the schema entirely — never a basket column), or its derived nameplate denominator is empty for this
    asset. A proxy into such a no-column slot self-heals to a blank instead of shipping a fabricated number.
    SCOPE: a validate-FAIL column (present in `failed` — real column, dead data) is LEFT to the existing gate's
    flag-and-reprompt path (the AI gets a chance to pick a live column first); this pass never usurps that. kind=time /
    const / text / $ctx / frame fields carry no measured column and are never blanked here (policed elsewhere)."""
    kind, src = f.get("kind"), f.get("source")
    if kind in ("time", "const", "text") or src in ("const", "frame", "$ctx"):
        return False, None
    if kind == "derived":
        base = [c for c in (f.get("base_columns") or [])]
        # an empty nameplate/rated denominator must NOT be used as a divisor — honest-blank the leaf
        if nameplate_missing and any(str(c).startswith("nameplate:") for c in base):
            return True, "nameplate rating denominator is empty for this asset — leaf honest-blanks"
        measured = [c for c in base if not str(c).startswith("nameplate:")]
        missing = [c for c in measured if c not in real and c not in failed]
        # PARTIAL BASIS KEEPS [corpus-replay precision]: the AI's declared base list is a CLAIM — the executor
        # resolves the fn's real inputs from its canonical derivation_binding row and every registry fn honest-
        # degrades per-input (missing register → None / the sanctioned recovery, never a fabrication). Blanking on
        # ONE over-declared base (activeEnergyTodayKwh declaring import+export on an import-only meter) pre-empted
        # REAL data the fill path computes (card-72 family, ~300 corpus FPs). Only a fn with NO measured basis at
        # all on this asset (every declared base absent) is a hallucinated bind and blanks here.
        if measured and len(missing) == len(measured):
            return True, f"derived base column(s) {missing} not measured on this asset — leaf honest-blanks"
        return False, None
    # a direct measured field (raw/bucketed/event) bound to a HALLUCINATED column (not in the schema at all) = a
    # proxy into a no-column slot; honest-blank it. (A validate-FAIL column stays for the existing gate to re-prompt.)
    col = f.get("column")
    if col and col not in real and col not in failed:
        return True, f"column {col!r} not in this asset's schema — leaf honest-blanks"
    return False, None


def _reuse_signature(f):
    """The binding that must not be smeared across distinct scalar slots: a derived field's fn, else a direct field's
    column. None for a field that carries no measured binding (const/time/text/columnless-$ctx buffer projection) —
    those are never a reuse defect. ★ A $ctx field that NAMES a column/fn IS a measured binding [DEFECT G closure]:
    the shared buffer holds one measurement per key, so smearing ONE $ctx key across ≥2 distinct-quantity scalars
    fabricates exactly like a live bind (cards 41/42 hvInputKw=lvOutputKw / expectedLoad=actualLoad) — no exemption."""
    if f.get("kind") == "derived" and f.get("fn"):
        return ("fn", f.get("fn"))
    if f.get("kind") in ("raw", "bucketed", "event") and f.get("column"):
        return ("col", f.get("column"))
    return None


_SEG = _re.compile(r"[^.\[\]]+")


def _slot_parent_chrome(exact_metadata, slot, key):
    """The `key` ('unit' / 'label') string CHROME sitting BESIDE a slot's leaf in the card's own exact_metadata
    skeleton (kpis[0].unit '°C' / kpis[2].label 'Events' beside kpis[i].value), or None. The skeleton is the VERBATIM
    design truth, so a slot whose own path/field carries no quantity still classifies (card 61: fn=worstPeakKw bound
    into a '°C' KPI cell; fn=loadFactorPct bound into the label-'Events' count cell — the sibling chrome is the only
    quantity evidence). Tolerates the `data.`-prefixed address form. Never raises."""
    if not isinstance(exact_metadata, dict) or not slot:
        return None
    toks = [t for t in _SEG.findall(str(slot))]
    if len(toks) < 2:
        return None
    for prefix in ((), ("data",)):
        node = exact_metadata
        ok = True
        for t in list(prefix) + toks[:-1]:
            k = int(t) if str(t).isdigit() else t
            try:
                node = node[k]
            except (KeyError, IndexError, TypeError):
                ok = False
                break
        if ok and isinstance(node, dict):
            u = node.get(key)
            if isinstance(u, str) and u.strip():
                return u
    return None


def _slot_parent_unit(exact_metadata, slot):
    return _slot_parent_chrome(exact_metadata, slot, "unit")


def _snake(name):
    """camelCase → snake_case ('hvInputKw' → 'hv_input_kw') for matching slot/metric names to schema column names."""
    toks = _re.findall(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z0-9]+|[A-Z]+", str(name or ""))
    return "_".join(t.lower() for t in toks if t)


def _slot_leaf_token(slot):
    toks = [t for t in _SEG.findall(str(slot or "")) if t and not t.isdigit() and t != "*"]
    return toks[-1].lower() if toks else ""


def _quantity_mismatch(f, col_by_name):
    """(True, reason) on a CONFIDENT cross-quantity bind — the slot's own path names one physical quantity
    (hotspotC → temperature, h5 → voltage-harmonic, readiness, faa, crestFactor, flickerPst, …) while the bound
    column / fn measures ANOTHER (active_power_total_kw → power; thd_current_r_pct → current-thd; a deviation/spread
    column re-purposed as crest-factor/flicker). Such a leaf must honest-blank: the meter has NO column of the slot's
    quantity, and a re-labelled number of a different quantity is a fabrication. Vocabulary + compatibility are
    layer2.quantity_class (DB rows quantity.unit_classes / quantity.name_classes, code-default mirror); an
    UNCLASSIFIED side never flags (no false positive on unfamiliar spellings).
    ★ NO $ctx EXEMPTION [DEFECT G closure — the pages 15/16/17 fabrication door]: a $ctx atom binding a wrong-quantity
    buffer key (power → hotspotC/lifeRemainingYears/battery-score) is just as fabricated as a live bind — the wall
    checks QUANTITY, so a structural $ctx atom (time/id/group-context, no quantity class on either side) never flags.
    ★ SLOT-SIDE UNIT FALLBACK: when the slot path itself is unclassified, the field's OWN declared display unit
    ('score', 'years', '°C') classifies the slot (the c51/c53 'unit=score series ← raw kW' family)."""
    kind = f.get("kind")
    # POLICE ANY FIELD THAT BINDS A REAL MEASURED SOURCE [card 78: a power COLUMN bound to the 'RTCC Mode' text KPI].
    # The wall used to police only raw/bucketed/derived, so a kind='text'/'kpi' field carrying a `column`/`fn` slipped
    # through as an un-checked cross-quantity proxy (declared kind was the escape hatch). A field is exempt ONLY when it
    # asserts NO measured quantity — a source-less label ($ctx / literal / kind=time timestamp / const). Same-quantity
    # binds still pass (compatible() below); only a genuine cross-quantity source into any slot honest-blanks.
    has_source = bool(f.get("column") or f.get("fn"))
    # kind=event is EXEMPT from the cross-quantity wall: an event COUNTS edge-crossings of its source column (the `edge`
    # threshold), so its OUTPUT quantity is a COUNT produced by the field kind — NOT the source column's quantity. A
    # 'starts' count ← active_power_total_kw is the number of times power crossed the start threshold (engine starts),
    # never a power reading; the executor can only ever emit a count here, so no wrong-quantity value can leak. A source
    # column of a different quantity than the count slot is BY DESIGN (you count crossings of power/voltage/…). An event
    # WITHOUT an edge is malformed and caught separately (gate_data_instructions: 'kind=event without edge'). This keeps
    # the kind=text/kpi proxy catch intact — a text/kpi field DISPLAYS the raw value, it does not transform it. [33cddcd
    # 'regardless of kind' swept kind=event in as collateral of the kind=text fix]
    if kind == "event":
        return False, None
    if not has_source and kind not in ("raw", "bucketed", "derived"):
        return False, None
    from layer2.quantity_class import (slot_class, unit_class, name_class, column_class, compatible,
                                       semantic_family_mismatch, source_role_mismatch)
    if f.get("fn") and not f.get("column"):
        src_name = f.get("fn")
        ccls, src = name_class(src_name), f"fn {src_name!r}"
    else:
        src_name = f.get("column")
        entry = col_by_name.get(src_name) or {"column": src_name}
        ccls, src = column_class(entry), f"column {src_name!r}"
    # NAME-LEVEL SEMANTIC-FAMILY WALL [card 65: kpis[0] 'Efficiency' = 5.3 ← fn loadFactorPct]: a same-DIMENSION pun
    # ('%' ↔ '%') slips the dimensional check below because 'percent' is WEAK — but a slot whose NAME (slot path /
    # metric / sibling label) claims a semantic family (efficiency / sfc / consumption / fuel — DB row
    # quantity.semantic_families) binds ONLY a same-family source (or a family-licensed class: consumption ← an
    # energy/power column is legit). Runs BEFORE the dimensional wall and independent of it — the slot may be
    # dimensionally unclassified yet still name its semantic. Unclaimed slots never flag.
    fam_hit, fams = semantic_family_mismatch(
        (f.get("slot"), f.get("metric"), f.get("_sibling_label")), src_name, ccls)
    if fam_hit:
        fam_txt = "/".join(fams)
        return True, (f"slot names the {fam_txt} semantic family — {src} is not a {fam_txt}-family source "
                      f"(a same-dimension stand-in is a fabrication); leaf honest-blanks")
    # slot-side classification order: the path's own tokens → the field's declared unit → the SKELETON's sibling unit
    # chrome (card 61: 'chart.kpis[0].value' + no field unit, but the payload cell says '°C' — that IS the slot's
    # quantity; a power fn bound there fabricates a temperature) → the SKELETON's sibling LABEL chrome (card 61 round
    # 3: the 'Events' KPI cell carries NO unit — its label names the count quantity the loadFactorPct bind punned)
    # → LAST the field's own declared METRIC name (the c55 family: metric='ups_transfers_30d' names a COUNT the
    # energy-counter fn punned — weakest evidence, the AI's own claim, so every chrome source outranks it; a metric
    # that merely echoes the bound column classifies identically and never flags).
    scls = slot_class(f.get("slot")) or unit_class(f.get("unit")) or unit_class(f.get("_sibling_unit")) \
        or name_class(f.get("_sibling_label")) or name_class(f.get("metric"))
    # DIMENSIONAL QUANTITY WALL — a confident cross-quantity bind blanks with its OWN reason (readiness ← load-factor,
    # power → °C). This owns EVERY cross-quantity case, so it runs BEFORE the same-quantity role wall below — a
    # bypass-metric readiness cell (ups_bypass_permissive_score ← loadFactorPct) is a readiness/load-factor mismatch
    # here, NOT a bypass role smear (the role wall targets ONLY the compatible-quantity gap the dimensional wall passes).
    if scls and not compatible(scls, ccls):
        return True, (f"{scls} not measured by this meter (no {scls} column) — {src} measures {ccls}, "
                      f"not {scls}; leaf honest-blanks")
    # NAME-LEVEL SOURCE-ROLE WALL [card 59: composite.points[*].bypassVoltageV ← voltage_avg]: a SAME-QUANTITY,
    # DIFFERENT-ROLE smear — the slot names a DEDICATED-SENSING role (bypass) while the source is the meter's plain
    # input/line reading of the SAME quantity (voltage↔voltage is compatible, so the dimensional wall above passes it).
    # Runs ONLY on a dimensionally-compatible (or unclassified) bind, so it never re-words a genuine cross-quantity
    # blank; a NON-dedicated role (input) and an unclaimed slot never flag. The meter has no bypass sensor → honest-blank.
    role_hit, roles = source_role_mismatch(
        (f.get("slot"), f.get("metric"), f.get("_sibling_label")), src_name)
    if role_hit:
        role_txt = "/".join(roles)
        return True, (f"slot names the {role_txt} source role — {src} is this meter's input/line reading, not a "
                      f"{role_txt} sensor (this meter has no {role_txt} column); leaf honest-blanks")
    return False, None


def _const_without_source(f, nameplate_missing):
    """(True, reason) for a kind=const NUMERIC field whose value resolves to NO real DB source — the 131 A /
    1000 kVA / fabricated-threshold class. A const ships ONLY when layer2.quantity_class.const_source resolves it:
      · a NAMEPLATE rating slot/metric (config.nameplate_slot_map — the executor substitutes the asset's REAL rating;
        kept unless the basket says the rating is KNOWN-empty, in which case the leaf blanks now);
      · an app_config `consts.<name>` row the field cites by metric/slot-leaf name with the row's own value
        (site-approved band/threshold/axis literals — stress_border_pct, hotspot_warn_c, …).
    Anything else is a seed/invented figure → the leaf honest-blanks. Non-numeric consts (status text) and valueless
    consts are policed elsewhere. ★ NO $ctx EXEMPTION [DEFECT G closure]: a numeric const is a baked literal wherever
    it claims to live — a $ctx-stamped const with no DB source is the same 120A/131A fabrication (card-38 thresholds)."""
    if f.get("kind") != "const":
        return False, None
    from layer2.quantity_class import numericish, const_source, structural_const_name
    v = f.get("value")
    if not numericish(v):
        return False, None
    # STRUCTURAL display/frame knobs [corpus-replay precision]: a const whose metric/slot-leaf names a pure render
    # parameter (decimals / opacity / selected index / layout / windowDays — quantity.structural_const_tokens) states
    # NO measurement; blanking it broke formatting/selection chrome without preventing any fabrication (~450 FPs).
    # A quantity-named const (131 A / 0.0 kW / 1461 kWh) never matches these tokens and stays policed below.
    if structural_const_name(f):
        return False, None
    # AXIS-CHROME CARVE-OUT [c49 LoadImpactChart]: a const whose SLOT names axis-geometry (yMax/yMin/yTicks bounds, or a
    # watchLines[*].value threshold line) is DISPLAY CHROME re-supplied from the card's design default, NOT a measured
    # reading — the post-fill yscale recomputes filled views from the real series, and a fixed threshold line legitimately
    # keeps its design literal. Match ANY path SEGMENT (not just the leaf) so watchLines[0].value is exempted while
    # stats[*].value — a real KPI reading with NO axis segment — stays gated. DB-tunable (quantity.axis_chrome_const_slots).
    _segs = {t.lower() for t in _re.findall(r"[^.\[\]]+", str(f.get("slot") or "")) if t and not t.isdigit() and t != "*"}
    if _axis_chrome_const_segs() & _segs:
        return False, None
    src = const_source(f)
    if src is None:
        return True, (f"const {v!r} has no real DB source (not a nameplate rating slot/metric, no matching "
                      "app_config consts.* row) — a literal in a data slot must come from asset_nameplate or "
                      "app_config; leaf honest-blanks")
    if src[0] == "nameplate" and nameplate_missing:
        return True, "nameplate rating is empty for this asset — const rating leaf honest-blanks"
    return False, None


def _axis_chrome_const_segs():
    """Slot path SEGMENTS whose const value is AXIS-GEOMETRY chrome (yMax/yMin/yTicks bounds + watchLines threshold
    lines) — exempt from the const-source gate: a design-default axis scale/threshold is display chrome, not a
    fabricated reading. ANY-segment match (catches watchLines[*].value; stats[*].value has no axis segment → stays
    gated). DB-driven (quantity.axis_chrome_const_slots) with a code-default mirror. [c49 carve-out]"""
    return {str(t).replace(" ", "").lower() for t in
            cfg("quantity.axis_chrome_const_slots", ["ymax", "ymin", "yticks", "watchlines"]) or []}


def _axis_slot_suffixes():
    return [str(t).lower() for t in cfg("quantity.axis_slot_tokens", ["ymin", "ymax", "miny", "maxy"]) or []]


# DIRECTIONAL extremum/range source vocabularies [corpus-replay precision]: an axis BOUND slot legitimately binds a
# source whose OWN name says it IS that bound — maxY ← current_max (the meter's real windowed maximum register),
# demandYMax ← fn worstPeakKw (a real windowed peak), maxY+minY ← fn voltageHistoryDomain / voltageStatutoryBand (a
# domain/band fn returns the range). 176 corpus FPs were exactly these; the degenerate/latest-sample reads
# (yMax=yMin ← active_power_total_kw, minY ← worstPeakKw) carry NO matching direction token and still blank.
def _axis_dir_tokens(key, default):
    return {str(t).replace(" ", "").lower() for t in cfg(key, default) or []}


def _axis_direction_ok(f, leaf):
    """True when the axis slot's DIRECTION (max-/min-bound from its own leaf) is answered by a source whose name
    carries a MATCHING extremum token (max←max/peak/worst/highest, min←min/lowest/floor) or a RANGE token
    (domain/band/range/bounds — a two-sided fn feeds both bounds). Token-exact on the fn/column name tokens."""
    from layer2.quantity_class import _tokens
    src_toks = set(_tokens(f.get("fn") if f.get("kind") == "derived" else f.get("column")))
    if not src_toks:
        return False
    allowed = _axis_dir_tokens("quantity.axis_range_source_tokens", ["domain", "band", "range", "bounds"])
    is_max, is_min = "max" in leaf, "min" in leaf
    if is_max:
        allowed |= _axis_dir_tokens("quantity.axis_max_source_tokens", ["max", "peak", "worst", "highest"])
    if is_min:
        allowed |= _axis_dir_tokens("quantity.axis_min_source_tokens", ["min", "lowest", "floor"])
    return bool(src_toks & allowed)


def _axis_source_mismatch(f, series_classes, col_by_name):
    """(True, reason) when a scalar AXIS-BOUND slot (yMin/yMax/… — config row quantity.axis_slot_tokens, suffix match
    so demandYMax qualifies) is emit-bound while the card co-emits a SERIES — axis bounds are chart GEOMETRY derived
    from the FILLED series (the post-fill yscale pass), never a live SAMPLE:
      · a cross-quantity source is the card-40-round-1 fabrication (yMin ← loadFactorWindowPct, a PERCENT, under
        185-199 kW bars → a 96.8 'kW' floor);
      · a SAME-quantity latest-sample read is the card-40-round-2 degenerate axis (yMax=yMin=183.0, the instantaneous
        kW snapshot copied into all four bounds → a zero-range axis under real 171-201 kW bars).
    Both drop; yscale recomputes the bounds from the real series min/max. A source whose own name IS the bound's
    direction (maxY ← current_max / worstPeakKw; minY ← current_min; either ← a domain/band/range fn — config rows
    quantity.axis_{max,min,range}_source_tokens) is a REAL measured extremum, not a sample — it KEEPS (the corpus-
    replay 176-FP release). No co-emitted series → the wall stays out (there is nothing to derive from), and only the
    classified cross-quantity rule could ever apply — an axis-less emission is left to the other walls."""
    kind = f.get("kind")
    if kind not in ("raw", "derived") or _is_series_anchor(f) or not series_classes:
        return False, None
    leaf = _slot_leaf_token(f.get("slot"))
    if not leaf or not any(leaf == t or leaf.endswith(t) for t in _axis_slot_suffixes()):
        return False, None
    from layer2.quantity_class import name_class, column_class, compatible
    if kind == "derived":
        cls, src = name_class(f.get("fn")), f"fn {f.get('fn')!r}"
    else:
        cls, src = column_class(col_by_name.get(f.get("column")) or {"column": f.get("column")}),             f"column {f.get('column')!r}"
    if cls and not any(compatible(cls, sc) for sc in series_classes):
        return True, (f"axis slot bound to {src} ({cls}) while this card's series measure "
                      f"{sorted(series_classes)} — the axis derives from the filled series instead; leaf honest-blanks")
    if _axis_direction_ok(f, leaf):
        return False, None                                       # a real measured extremum/domain of the series' own quantity
    return True, (f"axis slot bound to a scalar read ({src}) — an axis bound is chart geometry derived from the "
                  "filled series (post-fill yscale), never a live sample; leaf honest-blanks")


def _expectation_tokens():
    return {str(t).lower() for t in cfg("quantity.expectation_slot_tokens",
                                        ["expected", "forecast", "predicted"]) or []}


def _expectation_direct_bind(f):
    """(True, reason) when an EXPECTATION-family slot (expected*/forecast*/predicted* — config row
    quantity.expectation_slot_tokens) binds a DIRECT measured column read: a live reading is never an 'expectation' —
    binding the same column to actualLoad AND expectedLoad fabricates a baseline that trivially always matches
    (card 42). A derivation (a computed band/model) may still fill such a slot; a direct read may not."""
    if f.get("kind") not in ("raw", "bucketed", "event") or not f.get("column"):
        return False, None
    toks = {t.lower() for seg in _SEG.findall(str(f.get("slot") or ""))
            for t in _re.findall(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z0-9]+|[A-Z]+", seg)}
    hit = toks & _expectation_tokens()
    if not hit:
        return False, None
    return True, (f"'{sorted(hit)[0]}' slot bound to live column {f.get('column')!r} — a measured reading is never an "
                  "expected/forecast value (it would trivially equal the actual); leaf honest-blanks")


def _topology_boundary_proxy(f):
    """(True, reason) when a field's slot/metric names a SYNTHETIC TOPOLOGY-PAIR quantity (the base columns of the
    scope='topology' derivation rows: hv_input_kw / lv_output_kw — computed ACROSS meters, never measured by one)
    while its bound column is a DIFFERENT single-meter column (card 41: the meter's own active_power_total_kw shipped
    as 'HV INPUT' beside a gap note saying hv_input_kw is not measured). The DB rows ARE the vocabulary — a new
    boundary pair is one seed row, no code."""
    if f.get("kind") not in ("raw", "bucketed") or not f.get("column"):
        return False, None
    try:
        from config.derivation_binding import topology_pair_columns
        topo = topology_pair_columns()
    except Exception:
        return False, None
    for name in (_slot_leaf_token(f.get("slot")), f.get("metric")):
        sn = _snake(name)
        if sn and sn in topo and f.get("column") != sn:
            return True, (f"{sn} is a topology boundary quantity (computed across meters, not measured by this one) — "
                          f"column {f.get('column')!r} is this meter's own reading, not {sn}; leaf honest-blanks")
    return False, None


def _time_axis_label_bind(f):
    """(True, reason) when a MEASURED field (raw/bucketed/derived on a column/fn) binds a series TIME-AXIS LABEL slot
    (points[*].label / .slot / .time — layer2.quantity_class.is_time_axis_label_slot): that leaf is the time-axis tick
    label, filled from the card's OWN bucket timestamps as a kind=time atom, never a measured column. Binding
    active_power_total_kw there renders negative kW AS x-axis time labels (card 59 secondary). A kind=time atom (the
    correct emission) carries no column and never reaches this wall — only a column/fn bind flags."""
    from layer2.quantity_class import is_time_axis_label_slot
    if f.get("kind") not in ("raw", "bucketed", "derived"):
        return False, None
    if not (f.get("column") or f.get("fn")):
        return False, None
    if not is_time_axis_label_slot(f.get("slot")):
        return False, None
    src = f"column {f.get('column')!r}" if f.get("column") else f"fn {f.get('fn')!r}"
    return True, (f"time-axis label slot bound to a measured {src} — a series time label is filled from the card's "
                  "own bucket timestamps (kind=time), never a measured column; leaf honest-blanks")


def _live_claim_without_source(f):
    """(True, reason) for a field that CLAIMS a LIVE reading (source=='live') of a metric but has NEITHER a column NOR a
    fn to read it from — a text/enum LITERAL shipped as though it were live telemetry. Card 78: a transformer with zero
    tap/rtcc telemetry emitted {kind:'text', metric:'rtcc_mode', source:'live', value:'AUTO', column:None, fn:None} and
    {metric:'status_tone', source:'live', value:'Nominal', column:None, fn:None} — 'AUTO'/'Nominal' then render as claimed
    live readings with no source behind them. Neither _const_without_source (numeric+kind=const only) nor fab_guards
    CLASS 3 (numeric only) catches a NON-numeric literal, so a string enum masquerading as live slips through.

    A field is fabricating a live reading iff it DECLARES source=='live' yet resolves NO real source (no column, no fn).
    A genuine live field always carries a column or a fn; a legitimate chrome/label const does NOT claim source=='live'
    (its source is const/frame/absent) — so this never blanks real telemetry or a static design label. DB-driven: the
    'live'/data source tokens come from a cfg list with a code default. Never raises."""
    try:
        from config.app_config import cfg
        live_srcs = {str(s).strip().lower() for s in cfg("gates.live_source_tokens", ["live", "data"]) if s}
    except Exception:
        live_srcs = {"live", "data"}
    if str(f.get("source") or "").strip().lower() not in live_srcs:
        return False, None
    if f.get("column") or f.get("fn"):
        return False, None
    v = f.get("value")
    if v in (None, "", "—"):
        return False, None
    return True, (f"{v!r} claims a live reading (source=live, metric={f.get('metric')!r}) but has no column and no fn — "
                  "no telemetry source exists for this leaf; honest-blanks")
