"""layer2/gates/honest_blank.py — enforce_honest_blank: the pass that SEQUENCES the per-field walls (walls.py)
over a card's data_instructions. Per-leaf degradation: it blanks FIELDS, never cards."""
from layer2.gates.basket import _bindable, _nameplate_missing
from layer2.gates.walls import (
    _is_series_anchor, _blankable_field, _reuse_signature, _slot_parent_chrome, _slot_parent_unit,
    _quantity_mismatch, _const_without_source, _axis_source_mismatch, _expectation_direct_bind,
    _topology_boundary_proxy, _time_axis_label_bind, _live_claim_without_source)

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
        bad, reason = _time_axis_label_bind(f)                               # RULE (iii-e) — time-axis label [c59]
        if bad:
            blanked.append(f"{slot}: {reason}")
            continue
        bad, reason = _const_without_source(f, npm_missing)                  # RULE (iv) — const-source guard
        if bad:
            blanked.append(f"{slot}: {reason}")
            continue
        bad, reason = _live_claim_without_source(f)                          # RULE (iv-b) — live-claim w/o source [card 78]
        if bad:
            blanked.append(f"{slot}: {reason}")
            continue
        f.pop("_sibling_unit", None)                                         # internal stamps never ship
        f.pop("_sibling_label", None)
        kept.append(f)
    data_instructions["fields"] = kept
    return blanked
