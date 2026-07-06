"""layer2/gates.py — DETERMINISTIC Layer-2 emit gates. exact_metadata = byte-identical defaults + no chrome (vs the
harvested ground truth); data_instructions = every field a real basket column / const / $ctx. [PROMPTS §L2 gates 2/3]

The byte-identity gate is LOAD-BEARING [META-02]: `enforce_exact_metadata` REVERTS any leaf the AI changed without
declaring it in `morphed` (or that leaked chrome) back to its byte-identical default, so the resting render is
GUARANTEED byte-identical to the harvested ground truth — a non-conforming payload never ships, it self-heals to the
default. [contract POST: ENFORCING byte-identity gate (revert non-conforming to default)]"""
import copy
from layer2.emit.metadata.split import split, DATA_SLOT
from config.app_config import cfg

# Tunable vocab of design-system "chrome" markers — a morphed value containing any of these is rejected as leaked
# chrome. DB-editable as gates.chrome_markers (json) so the deny-list can be tuned without a code change.
_CHROME = cfg("gates.chrome_markers",
              ["=>", "function(", "function (", "React.", "onClick", "px solid", "rgba("])


def _is_chrome(v):
    return isinstance(v, str) and any(t in v for t in _CHROME)


def gate_exact_metadata(exact_metadata, default_payload, morphed=None):
    """Every metadata leaf present + byte-identical to the default (unless declared in `morphed`); no data leaf, no chrome."""
    morphed = set(morphed or [])
    skeleton, _data_paths = split(default_payload)
    issues = []

    def walk(skel, got, path):
        if skel == DATA_SLOT:                                   # a DATA leaf must NOT be authored as metadata
            if got is not None:
                issues.append(f"{path}: DATA leaf authored in exact_metadata (belongs to data_instructions)")
            return
        if isinstance(skel, dict):
            if not isinstance(got, dict):
                issues.append(f"{path}: missing metadata object"); return
            for k, v in skel.items():
                walk(v, got.get(k), f"{path}.{k}" if path else k)
            for k in got:
                if k not in skel:
                    issues.append(f"{path}.{k}: invented metadata key (not in default shape)")
            return
        if isinstance(skel, list):
            if not isinstance(got, list) or len(got) != len(skel):
                issues.append(f"{path}: metadata array shape changed"); return
            for i, v in enumerate(skel):
                walk(v, got[i], f"{path}[{i}]")
            return
        # leaf — a byte-identical default is GROUND TRUTH (OK even if it is a default rgba()/hex colour the harvested
        # payload legitimately ships, e.g. a radar polygonFill or a legend colour). Only a CHANGED value is policed: an
        # undeclared change is a byte-identity violation; a declared morph must not INTRODUCE chrome.
        if got == skel:
            return
        if path not in morphed:
            issues.append(f"{path}: byte-identical-default violation (got {got!r}, default {skel!r})")
        elif _is_chrome(got):
            issues.append(f"{path}: design-system chrome leaked into a morphed value ({got!r})")

    walk(skeleton, exact_metadata, "")
    return (not issues), issues


def enforce_exact_metadata(exact_metadata, default_payload, morphed=None):
    """LOAD-BEARING byte-identity enforcement [META-02]. Walk the default SKELETON and REBUILD a payload where every
    leaf is the byte-identical default UNLESS it was legitimately morphed (declared in `morphed` AND chrome-free). Any
    undeclared change, invented key, shape drift, or chrome-leaking morph is DROPPED (reverted to default). The result
    is guaranteed to pass gate_exact_metadata. Returns (safe_exact_metadata, reverted_paths[]).

    This never fabricates: it only ever restores the harvested ground-truth default; a genuinely story-driven, chrome-
    free, declared morph survives verbatim."""
    morphed = set(morphed or [])
    skeleton, _data_paths = split(default_payload)
    reverted = []

    def rebuild(skel, got, path):
        if skel == DATA_SLOT:
            return None                                         # DATA leaf stays elided (filled live on the frontend)
        if isinstance(skel, dict):
            g = got if isinstance(got, dict) else {}
            return {k: rebuild(v, g.get(k), f"{path}.{k}" if path else k) for k, v in skel.items()}
        if isinstance(skel, list):
            if not isinstance(got, list) or len(got) != len(skel):
                if isinstance(got, list) and got != skel:
                    reverted.append(path)                       # array shape drift → revert whole array to default
                return copy.deepcopy(skel)
            return [rebuild(v, got[i], f"{path}[{i}]") for i, v in enumerate(skel)]
        # leaf
        if got == skel:
            return skel                                         # byte-identical (ground truth) — keep
        if path in morphed and not _is_chrome(got):
            return got                                          # legitimate declared, chrome-free morph — keep
        reverted.append(path)                                   # undeclared change / chrome leak → revert to default
        return skel

    safe = rebuild(skeleton, exact_metadata, "")
    return safe, reverted


def enforce_free_metadata(ai_exact_metadata):
    """NO-DEFAULT enforce [folded scrub]. A card with NO harvested card_payloads row (no stored payload_stripped) has
    the AI author exact_metadata off the seed-bearing contract payload_schema_json — so its data leaves ('540.9 kW')
    and clock labels ('13:14:10') would ship verbatim. There is NO stored seedless skeleton to revert against, so
    gate_exact_metadata/enforce_exact_metadata (which need a default ref) cannot cover this case. This is the ONE
    check that path needs: data leaves → typed placeholders (leaf_classify) + narrative/clock/provenance scrubbed.
    It REUSES the canonical strip worker (grounding.default_assemble._strip_and_scrub) — the SAME transform the build
    script persists — so there is no second strip implementation and no runtime strip_to_placeholders caller. Chrome
    (labels/booleans/colors) is untouched; never raises."""
    if not isinstance(ai_exact_metadata, (dict, list)):
        return ai_exact_metadata
    try:
        from grounding.default_assemble import _strip_and_scrub   # shared worker (build script owns strip_to_placeholders)
        return _strip_and_scrub(ai_exact_metadata)
    except Exception:
        return ai_exact_metadata


def _bindable(basket):
    """(real, failed) — the columns Layer 2 may bind. The pre-L2 validation verdict is folded into the basket
    (validate/build._fold_into_basket); a validate-FAIL column (mostly-null / absent on the meter) is UNBINDABLE and
    gates exactly like a hallucinated one, carrying the validate reason so the leaf honest-blanks with a real cause
    (per-leaf degradation). A basket that never saw validation (no verdict keys) binds as before."""
    real, failed = set(), {}
    for c in (basket.get("columns") or []):
        col = c.get("column")
        if not col:
            continue
        if c.get("verdict") == "fail":
            failed[col] = "; ".join(c.get("validate_reasons") or []) or "failed pre-L2 data validation"
        else:
            real.add(col)
    return real, failed


def _col_issue(i, col, failed):
    if col in failed:
        return f"fields[{i}] column {col!r} failed pre-L2 data validation ({failed[col]}) — leaf honest-blanks"
    return f"fields[{i}] column {col!r} not in basket (hallucinated)"


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
    if kind not in ("raw", "bucketed", "derived"):
        return False, None
    from layer2.quantity_class import (slot_class, unit_class, name_class, column_class, compatible,
                                       semantic_family_mismatch)
    if kind == "derived":
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
    if not scls:
        return False, None
    if compatible(scls, ccls):
        return False, None
    return True, (f"{scls} not measured by this meter (no {scls} column) — {src} measures {ccls}, "
                  f"not {scls}; leaf honest-blanks")


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
    src = const_source(f)
    if src is None:
        return True, (f"const {v!r} has no real DB source (not a nameplate rating slot/metric, no matching "
                      "app_config consts.* row) — a literal in a data slot must come from asset_nameplate or "
                      "app_config; leaf honest-blanks")
    if src[0] == "nameplate" and nameplate_missing:
        return True, "nameplate rating is empty for this asset — const rating leaf honest-blanks"
    return False, None


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


def enforce_honest_blank(data_instructions, basket, *, is_group_card=False, exact_metadata=None):
    """In-place honest-blank pass over data_instructions.fields (mutates + returns telemetry list). Four GENERIC,
    data-driven rules:
      (i) a field whose OWN measured column / derived base-column is ABSENT from the asset basket (or whose nameplate
          denominator is empty) is DROPPED — the slot renders an honest blank instead of a proxy number;
     (ii) when the SAME fn / column is bound to ≥2 DISTINCT-QUANTITY SCALAR value slots (their CLASSIFIED quantities
          differ — no longer their metric strings: a same-quantity annotation re-bind maxY+maxLine.value ← current_max
          is ONE measurement rendered twice, never the defect) with NO co-bound series anchor AND an UNCLASSIFIED
          bind, only the FIRST such scalar is kept (a classified bind's cross-quantity cells are blanked per-cell by
          the QUANTITY WALL (iii) with their own reasons — the c54/c55/c57 score/count families land there);
    (iii) QUANTITY WALL — a field whose slot names ONE physical quantity while its bound column/fn measures ANOTHER
          (power into hotspotC/faa/readiness; thd_current into an h5 voltage-harmonic cell; deviation/spread into
          crest-factor/flicker) is DROPPED — 'X not measured by this meter (no X column)' (layer2.quantity_class,
          DB-vocab-driven, unclassified sides never flag);
     (iv) CONST-SOURCE — a kind=const NUMERIC field whose value resolves to NO real DB source (not a nameplate rating
          per config.nameplate_slot_map, no matching app_config consts.* row) is DROPPED — a literal in a data slot
          is only ever a REAL rating or a site-approved config row, never a Storybook seed (the 131 A / 1000 kVA class).
    ★ GROUP/$ctx BYPASS CLOSED [DEFECT G — 19 G-family cards fabricated through the old doors]: the walls (ii)/(iii)/
    (iv) run on EVERY card, group or not, and on $ctx-sourced fields too — a $ctx atom binding a wrong-quantity buffer
    key / an unsourced const fabricates identically (pages 15/16/17: power as °C/years/aging/battery-scores). ONLY the
    basket-membership rule (i) keeps its per-FIELD $ctx/const/frame exemption ($ctx buffer keys are metric keys, not
    basket columns — see _blankable_field), so genuinely-structural $ctx uses (time atoms, group-context projections,
    unclassified buffer keys) still pass: the walls check QUANTITY, and unclassified = compatible. A ROSTER emission is
    untouched here (gate_roster owns it) — but a group/roster card's explicit fields[] pass the same walls as anyone's.
    `is_group_card` is kept for caller/API compatibility (no longer a bypass).
    Kept fields keep their order. Returns [reason strings] for di._honest_blanked (telemetry, never a card gate)."""
    fields = data_instructions.get("fields")
    if not isinstance(fields, list) or not fields:
        return []
    real, failed = _bindable(basket)
    col_by_name = {c.get("column"): c for c in (basket.get("columns") or []) if isinstance(c, dict) and c.get("column")}
    blanked, kept = [], []
    # SLOT-SIDE SIBLING UNIT + LABEL [card 61]: stamp each field with the skeleton's own chrome beside its leaf
    # (kpis[0].unit '°C'; kpis[2].label 'Events') so the quantity wall classifies slots whose path/field carry no
    # quantity token. Telemetry-transparent (internal '_sibling_*' keys the producer/consumers never read).
    if isinstance(exact_metadata, dict):
        for f in fields:
            if not isinstance(f, dict):
                continue
            if not f.get("unit"):
                u = _slot_parent_unit(exact_metadata, f.get("slot"))
                if u:
                    f["_sibling_unit"] = u
            lb = _slot_parent_chrome(exact_metadata, f.get("slot"), "label")
            if lb:
                f["_sibling_label"] = lb
    # AXIS COHERENCE input [card 40]: the quantities this card's SERIES actually measure (co-emitted anchors).
    from layer2.quantity_class import name_class as _ncls, column_class as _ccls, _weak as _wk
    series_classes = set()
    for f in fields:
        if not isinstance(f, dict) or not _is_series_anchor(f):
            continue
        if f.get("kind") == "derived":
            c = _ncls(f.get("fn"))
        else:
            c = _ccls(col_by_name.get(f.get("column")) or {"column": f.get("column")}) if f.get("column") else None
        if c and c.lower() not in _wk():
            series_classes.add(c)
    # RULE (ii) — a reuse group with ≥2 DISTINCT-QUANTITY scalar cells (no series anchor) keeps at most ONE scalar.
    # PRECISION REWORK [corpus replay: 450 FP suspects]: distinctness is the cells' CLASSIFIED quantity (the same
    # slot-side evidence chain the quantity wall uses), no longer their metric STRINGS — a same-quantity annotation
    # re-bind (maxY + maxLine.value + maxLine.label.value ← current_max; summary.value + sideValue ← current_avg) is
    # ONE measurement legitimately rendered in several places, never the smear defect. When the shared bind's OWN
    # quantity is classified, the QUANTITY WALL (iii) below blanks each cross-quantity cell individually with its own
    # honest reason (the c54/c57 score/count families land there); rule (ii) fires only for an UNCLASSIFIED bind
    # smeared across cells that classify ≥2 distinct quantities — there it keeps the first scalar, drops the rest.
    from layer2.quantity_class import slot_class as _scls_fn, unit_class as _ucls_fn

    def _slot_side(f):
        return _scls_fn(f.get("slot")) or _ucls_fn(f.get("unit")) or _ucls_fn(f.get("_sibling_unit")) \
            or _ncls(f.get("_sibling_label")) or _ncls(f.get("metric"))

    groups = {}
    for idx, f in enumerate(fields):
        sig = _reuse_signature(f)
        if sig is not None:
            groups.setdefault(sig, []).append(idx)
    reuse_drop = set()
    for sig, idxs in groups.items():
        scalars = [i for i in idxs if not _is_series_anchor(fields[i])]
        anchored = any(_is_series_anchor(fields[i]) for i in idxs)
        if len(scalars) < 2 or anchored:
            continue
        distinct_classes = {c for c in (_slot_side(fields[i]) for i in scalars) if c}
        if len(distinct_classes) < 2:
            continue                                                # same-quantity / unclassified reuse ≠ smear
        src_cls = _ncls(sig[1]) if sig[0] == "fn" else _ccls(col_by_name.get(sig[1]) or {"column": sig[1]})
        if src_cls:
            continue                                                # classified bind → wall (iii) blanks per cell
        for i in scalars[1:]:                                       # unclassified bind, distinct claims: keep first
            reuse_drop.add(i)
    # RULE (i) + apply (ii)/(iii)/(iv): rebuild fields, dropping honest-blank / reuse-proxy / cross-quantity /
    # sourceless-const fields, recording a per-leaf reason for each.
    npm_missing = _nameplate_missing(data_instructions, basket)
    for idx, f in enumerate(fields):
        slot = f.get("slot")
        if idx in reuse_drop:
            sig = _reuse_signature(f)
            blanked.append(f"{slot}: {sig[0]}={sig[1]!r} reused across distinct scalar slots — honest-blank "
                           "(a single measurement cannot answer multiple distinct-quantity cells)")
            continue
        bad, reason = _blankable_field(f, real, failed, npm_missing)
        if bad:
            blanked.append(f"{slot}: {reason}")
            continue
        bad, reason = _quantity_mismatch(f, col_by_name)                     # RULE (iii) — quantity wall
        if bad:
            blanked.append(f"{slot}: {reason}")
            continue
        bad, reason = _axis_source_mismatch(f, series_classes, col_by_name)  # RULE (iii-b) — axis coherence [c40]
        if bad:
            blanked.append(f"{slot}: {reason}")
            continue
        bad, reason = _expectation_direct_bind(f)                            # RULE (iii-c) — expectation wall [c42]
        if bad:
            blanked.append(f"{slot}: {reason}")
            continue
        bad, reason = _topology_boundary_proxy(f)                            # RULE (iii-d) — boundary wall [c41]
        if bad:
            blanked.append(f"{slot}: {reason}")
            continue
        bad, reason = _const_without_source(f, npm_missing)                  # RULE (iv) — const-source guard
        if bad:
            blanked.append(f"{slot}: {reason}")
            continue
        f.pop("_sibling_unit", None)                                         # internal stamps never ship
        f.pop("_sibling_label", None)
        kept.append(f)
    data_instructions["fields"] = kept
    return blanked


def _nameplate_missing(data_instructions, basket):
    """True when the asset's nameplate rating is empty (so a nameplate:* denominator must not be used). DATA-DRIVEN
    from the basket (the caller folds nameplate availability into basket['nameplate'] when known) with a safe default:
    absent info ⇒ treat as PRESENT (do NOT blank a nameplate fn on unknown info — the executor's own fill-time
    honest-degrade still guards the divide-by-empty). Cached per call via the passed dict — no live DB in the gate."""
    npm = basket.get("nameplate")
    if isinstance(npm, dict) and "rated_present" in npm:
        return not npm.get("rated_present")
    return False


def gate_data_instructions(data_instructions, basket, *, is_group_card=False, fields_optional=False,
                           answerability=None, exact_metadata=None):
    # HONEST-BLANK PRE-PASS (SEAM 2): drop proxy / reused-binding / no-column fields IN PLACE before validation, so a
    # slot the asset can't measure ships an honest blank, not a fabricated number. Telemetry rides di._honest_blanked
    # (NOT a card gate — per-leaf degradation); the reduced fields[] is then validated below as usual.
    # `exact_metadata` (optional) = the card's authored skeleton — the sibling-unit slot-quantity evidence [card 61].
    _hb = enforce_honest_blank(data_instructions, basket, is_group_card=is_group_card, exact_metadata=exact_metadata)
    if _hb:
        existing = data_instructions.get("_honest_blanked") or []
        data_instructions["_honest_blanked"] = existing + _hb
    real, failed = _bindable(basket)
    issues = []
    fields = data_instructions.get("fields") or []
    if not fields:
        # A pure-chrome / special-renderer card (handling_class in app_config gates.fields_optional_classes: nav_index
        # chrome, narrative_ai/topology_sld/asset_3d whose DATA is built by run_special, not fields[]) legitimately
        # carries fields: [] — its render is its exact_metadata / a widget envelope, nothing to bind. Any fields it
        # DOES emit are still fully policed below.
        # A member-scope ROSTER emission is a data binding too: fields:[] beside a non-empty data_instructions.roster
        # CONFORMS — the card's DATA rides the roster interpreter, not fields[], and gate_roster normalizes that
        # roster to the recipe truth right after this gate. Flagging it shipped a STALE payload_error on cards whose
        # normalized render was fine (the page-01 card-5 class: 'fields is empty' + already-backfilled roster issues).
        # ★ HONEST-NONE CARVE-OUT [card 74, empty-fields family]: an emission that DECLARES answerability="none" (or
        # arrives with an EMPTY column basket — the asset logs no metric columns, so there is literally nothing to
        # bind) is the AI's CORRECT honest escape, not a defect. Stamping it a card-blocking payload_error was a
        # verdict acting as a render gate (mandate breach: per-LEAF degradation, verdicts are telemetry). The card
        # renders its metadata frame with honest-blank leaves; the "none" still drives the reflect re-route.
        # ★ GATE-EMPTIED CARVE-OUT [card 52, quantity-wall family]: when enforce_honest_blank itself removed every
        # field (_honest_blanked non-empty — proxies/consts the wall correctly killed), the emptiness is the GATE's
        # honest verdict, not an emit defect. The card renders its skeleton with per-leaf reasons; erroring here would
        # punish the AI for the gate doing its job (verdicts are telemetry, never a render gate).
        if not fields_optional and not data_instructions.get("roster") \
                and not data_instructions.get("_honest_blanked") \
                and not (str(answerability or "").lower() == "none" or not real):
            issues.append("data_instructions.fields is empty")
    for i, f in enumerate(fields):
        kind, src, col = f.get("kind"), f.get("source"), f.get("column")
        # LITERAL / CHROME fields — a const value or a text label. The literal lives in exact_metadata, NOT a data
        # column; demanding a column here wrongly rejected every "Live Health" status text (source=='const' too).
        # source=='frame' = a fan-out / list-structure field the FRONTEND fills from the live frame (column_override
        # dropped its hallucinated column) — no column to bind here either.
        if kind in ("const", "text") or src in ("const", "frame"):
            if kind == "const" and f.get("value") is None:
                issues.append(f"fields[{i}] kind=const without a value")
            continue
        # TIME-AXIS field — the emit contract is {slot, kind:"time", role, source} with NO column and NO metric: the
        # executor fills the leaf from the card's OWN bucket-timestamp axis (fill._is_time_field →
        # _anchor_timestamps; the panel renderer rides the same axis), never from a measured column. Demanding a
        # resolved column here rejected every CONFORMING time emission ('fields[i] kind=time missing a resolved
        # column' — the cards 56/59 class). A timestamp-ish column it may still carry ('ts') is the executor's
        # compat net, not a basket column — nothing to police.
        if kind == "time":
            continue
        if src == "$ctx":
            if not is_group_card:
                issues.append(f"fields[{i}] source=$ctx on a non-group card")
            continue
        # DERIVED — computed by a fn (the derivation LIBRARY) over base_columns; it has NO single resolved column.
        # Validate it carries the fn + its base inputs instead of demanding a column.
        if kind == "derived":
            if not f.get("fn"):
                issues.append(f"fields[{i}] kind=derived without fn")
            if not f.get("base_columns"):
                issues.append(f"fields[{i}] kind=derived without base_columns")
            continue
        # DIRECT live/test-db column fields.
        if src not in ("live", "test-db"):
            issues.append(f"fields[{i}] bad source {src!r} (want live|test-db|const|$ctx)")
        if col and col not in real:
            issues.append(_col_issue(i, col, failed))
        if not col:
            issues.append(f"fields[{i}] kind={kind} missing a resolved column")
        if kind == "event" and not f.get("edge"):
            issues.append(f"fields[{i}] kind=event without edge")
    return (not issues), issues


def gate_roster(roster, roster_spec, basket):
    """Validate + normalize data_instructions.roster against the card's card_fill_recipe row. [package §2d]

    Returns (ok, issues, normalized_roster). The recipe row is AUTHORITATIVE — the AI's ONLY authority is the COLUMN
    inside a col/delta/phase_mean/prefer_abs binding (each named column must exist VERBATIM in the basket); slot paths,
    element keys, role_filter/group_by/order/caps and reducers/floors are FIXED by the recipe. VALIDATION, not
    correction: a non-conforming part is reported (telemetry) and the recipe truth ships in its place; a clean column
    choice is folded in. Recipe slots the AI omitted are appended verbatim (deterministic fail-open, META-08 pattern),
    so an AI that emits no roster still ships the full recipe-derived roster — per-leaf degradation, never a blank card."""
    real, _failed = _bindable(basket)          # validate-FAIL columns are unbindable here too (pre-L2 verdict)
    spec_slots = {s.get("slot"): s for s in (roster_spec or {}).get("slots") or [] if isinstance(s, dict)}
    issues, normalized = [], []
    if roster and not spec_slots:
        return False, ["roster emitted for a card with no roster recipe"], []
    for i, r in enumerate(roster or []):
        if not isinstance(r, dict):
            issues.append(f"roster[{i}] is not an object"); continue
        s = spec_slots.get(r.get("slot"))
        if s is None:
            issues.append(f"roster[{i}] slot {r.get('slot')!r} not in card recipe"); continue
        if r.get("scope") not in (None, "members"):
            issues.append(f"roster[{i}] bad scope {r.get('scope')!r}")
        for k in ("role_filter", "group_by", "order"):
            if r.get(k) not in (None, s.get(k)):
                issues.append(f"roster[{i}] {k}={r.get(k)!r} != recipe {s.get(k)!r}")
        if r.get("cap") is not None and s.get("cap") is not None and r["cap"] > s["cap"]:
            issues.append(f"roster[{i}] cap {r['cap']} > recipe cap {s['cap']}")
        # element: keys ⊆ recipe keys; a recipe honest-null key STAYS null; every named column ∈ basket (verbatim-real)
        merged = {k: (dict(v) if isinstance(v, dict) else v) for k, v in (s.get("element") or {}).items()}
        for k, v in (r.get("element") or {}).items():
            if k not in merged:
                issues.append(f"roster[{i}].element key {k!r} not in recipe (invented)"); continue
            b = {"b": "col", "c": v} if isinstance(v, str) else (v if isinstance(v, dict) else {})
            spec_b = merged[k] if isinstance(merged[k], dict) else {}
            if spec_b.get("b") == "null" and b.get("b") != "null":
                issues.append(f"roster[{i}].element {k!r} is honest-null in recipe; column binding rejected"); continue
            if b.get("c") == spec_b.get("c") and list(b.get("cs") or []) == list(spec_b.get("cs") or []):
                continue                                # verbatim repeat of the recipe's own binding = recipe truth
                # (member-scope columns live on MEMBER tables — the panel's own basket may not carry them; only a
                #  column the AI CHANGED is its decision, and THAT must be a real basket column below)
            bad = [c for c in ([b.get("c")] if b.get("c") else []) + list(b.get("cs") or []) if c not in real]
            if bad:
                issues += [f"roster[{i}].element {k!r} column {c!r} not in basket (hallucinated)" for c in bad]
                continue
            merged[k] = {**spec_b, **{kk: b[kk] for kk in ("c", "cs") if kk in b}}   # clean column choice folds in
        # reducers/floors are FIXED by the recipe — the AI may not move thresholds or invent aggregations
        for agg_key in ("agg", "group_agg", "section_agg"):
            _r_agg = r.get(agg_key)
            if not isinstance(_r_agg, dict):
                continue                                       # a string/list agg emission is normalized from the recipe, never indexed
            for k in _r_agg:
                if (s.get(agg_key) or {}).get(k) != _r_agg[k]:
                    issues.append(f"roster[{i}].{agg_key}[{k!r}] differs from recipe (thresholds/reducers are fixed)")
        norm = dict(s)                                          # recipe wins wholesale …
        if "element" in s:
            norm["element"] = merged                            # … with the AI's validated columns folded in
        normalized.append(norm)
    # backfill: recipe slots the AI omitted ship VERBATIM (deterministic fail-open — full roster even on emit failure)
    emitted = {r.get("slot") for r in (roster or []) if isinstance(r, dict)}
    normalized += [dict(s) for slot, s in spec_slots.items() if slot not in emitted]
    return (not issues), issues, normalized
