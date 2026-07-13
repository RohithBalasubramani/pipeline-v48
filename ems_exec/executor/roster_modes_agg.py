"""ems_exec/executor/roster_modes_agg.py — the SCALAR/AGGREGATE roster modes: `aggregates` (a reducer map merged onto
the slot dict), `scalar` (ONE fleet reducer result at a single scalar leaf) and `entries` (a fixed id-keyed array of
per-QUANTITY reducers). All vocabulary arrives in the recipe rows — zero card knowledge. roster.py dispatches +
re-exports byte-compatibly. [atomic]
"""
from __future__ import annotations

import copy

from ems_exec.executor import reducers as _reducers
from ems_exec.executor.roster_paths import _targets
from ems_exec.executor.roster_template import _seedfree, _default_list_at
from ems_exec.executor.roster_eval import (
    _select, _slot_window, _eval_elements, _context_vals, _shared_element)


def _member_in_section(member, tok):
    """True iff the member belongs to bus-section token `tok` — the SAME equipment.mfm dictionary lookup the rest of
    the overlay uses (data/equipment/sections), zero card knowledge. Unmapped member / lookup miss → not in-section."""
    try:
        from data.equipment.sections import section_of
        return str(section_of(member.get("table")) or "").upper() == str(tok).upper()
    except Exception:
        return False


def _compute_aggs(aggs, els_for, element_spec, state):
    """Run the closed reducer map over an element set (els_for(rf, ro) → elements). Sibling-referencing reducers
    (alias/sum_of/difference/ratio_pct) run last over `computed`. Returns {agg_key: value}. Pure — no payload write,
    so it serves BOTH the union roll-up and each per-section roll-up (member set differs, math identical)."""
    slot_rf = None
    computed, late = {}, {}
    for k, aspec in (aggs or {}).items():
        if not isinstance(aspec, dict):
            continue
        if (aspec.get("agg") or "").strip().lower() in ("alias", "sum_of", "difference", "ratio_pct"):
            late[k] = aspec
            continue
        rf = aspec.get("role_filter") or slot_rf
        computed[k] = _reducers.reduce(aspec, els_for(rf), computed=computed, context=_context_vals(state),
                                       element_spec=element_spec, policy=state["policy"])
    for k, aspec in late.items():
        computed[k] = _reducers.reduce(aspec, [], computed=computed, context=_context_vals(state),
                                       element_spec=element_spec, policy=state["policy"])
    return computed


def _aggregates_slot(payload, spec, state, default_payload):
    element_spec = spec.get("element") if isinstance(spec.get("element"), dict) and spec.get("element") \
        else _shared_element(state)
    slot_rf = spec.get("role_filter") or "all"
    slot_ro = bool(spec.get("reporting_only"))
    slot_win = _slot_window(spec, state)
    pairs_cache = {}

    def _pairs(rf):
        rf = rf or slot_rf
        if rf not in pairs_cache:
            pairs_cache[rf] = _eval_elements(element_spec, _select(spec, state, role_filter=rf, reporting_only=slot_ro),
                                             state, window=slot_win)                    # [(member, element), …]
        return pairs_cache[rf]

    def _els_for(member_filter):
        def _f(rf):
            return [e for (m, e) in _pairs(rf) if member_filter is None or member_filter(m)]
        return _f

    computed = _compute_aggs(spec.get("agg") or {}, _els_for(None), element_spec, state)

    # ★ PER-SECTION KPI STRIP [per-section aggregates, N-generic]: when the gate marked this slot `_sections`, recompute
    # the SAME reducer map once per section (members filtered to that section) → stats.sections = {tok: {agg_key:value}}.
    # Iterates the token list, so it holds for 2, 3, 4, … sections. The union `computed` still ships (the strip keeps a
    # combined view); the host renders each KPI per section from stats.sections. A section with no member → honest nulls.
    sect_toks = spec.get("_sections")
    if isinstance(sect_toks, list) and sect_toks:
        computed["sections"] = {
            str(tok): _compute_aggs(spec.get("agg") or {}, _els_for(lambda m, t=tok: _member_in_section(m, t)),
                                    element_spec, state)
            for tok in sect_toks}

    for container, key, _marker in _targets(payload, default_payload, spec.get("slot")):
        cur = container.get(key)
        if not isinstance(cur, dict):
            container[key] = {}
            cur = container[key]
        cur.update(copy.deepcopy(computed))


def _scalar_slot(payload, spec, state, default_payload):
    """Write ONE fleet reducer result directly to a SCALAR leaf (the aggregates machinery for a fixed-index KPI tile
    whose slot is a single value, e.g. `stats.0.value` — a scalar, not a dict to merge onto). Same closed reducer
    vocabulary + element eval + role/reporting filters as `aggregates`; the single result lands at the slot path.
    Honest-null: an empty reporting set → None (the FE display-dashes it), never a fabricated 0."""
    element_spec = spec.get("element") if isinstance(spec.get("element"), dict) and spec.get("element") \
        else _shared_element(state)
    aspec = spec.get("agg") if isinstance(spec.get("agg"), dict) else {}
    rf = aspec.get("role_filter") or spec.get("role_filter") or "all"
    ro = bool(spec.get("reporting_only"))
    els = [e for (_m, e) in _eval_elements(element_spec, _select(spec, state, role_filter=rf, reporting_only=ro),
                                           state, window=_slot_window(spec, state))]
    value = _reducers.reduce(aspec, els, computed={}, context=_context_vals(state),
                             element_spec=element_spec, policy=state["policy"])
    for container, key, _marker in _targets(payload, default_payload, spec.get("slot")):
        container[key] = copy.deepcopy(value)


def _entries_slot(payload, spec, state, default_payload):
    """Rebuild a FIXED id-keyed array leaf whose entries are per-QUANTITY (not per-member) reducers — the KPI-strip /
    tick-segment shape (metrics [Active/Reactive/SEC], segments [Active/Reactive]) where each entry sums a DIFFERENT
    member column with the quantity-correct reducer. Members are read ONCE via the slot's shared `element` (the delta /
    col bindings); then EACH declared `entries[i]` reduces the SAME evaluated element set by its OWN agg (either a single
    `agg`→`value_key`, or an `aggs` map {key: agg-spec}) and lands the result in that entry's value key(s). Every rebuilt
    entry is CLONED onto its DEFAULT array entry — matched by `id_key` (default 'id'), else index — so its chrome
    (color / label / unit / id) survives byte-faithful. Honest-null: an empty reporting set → None per entry (the FE
    display-dashes it); a `{"agg":"const","v":null}` entry (no such neuract column — e.g. SEC needs production tonnage,
    absent) stays an honest blank, never a fabricated 0. Generic: ZERO card knowledge — the ids/keys/reducers all arrive
    in the recipe row. [reused by every EnergyProgressCard-shaped fixed KPI array]"""
    slot = spec.get("slot")
    entries = spec.get("entries") if isinstance(spec.get("entries"), list) else []
    if not slot or not entries:
        return
    id_key = spec.get("id_key") or "id"
    element_spec = spec.get("element") if isinstance(spec.get("element"), dict) and spec.get("element") \
        else _shared_element(state)
    rf = spec.get("role_filter") or "all"
    ro = bool(spec.get("reporting_only"))
    els = [e for (_m, e) in _eval_elements(element_spec, _select(spec, state, role_filter=rf, reporting_only=ro),
                                           state, window=_slot_window(spec, state))]
    dlist = _default_list_at(default_payload, slot)                 # default entries (chrome templates), matched by id
    dby_id = {d.get(id_key): d for d in dlist if isinstance(d, dict) and d.get(id_key) is not None}
    rebuilt = []
    for n, edef in enumerate(entries):
        if not isinstance(edef, dict):
            continue
        eid = edef.get(id_key)
        tmpl = dby_id.get(eid) or (dlist[n] if n < len(dlist) and isinstance(dlist[n], dict) else None)
        entry = _seedfree(tmpl) if isinstance(tmpl, dict) else {}
        entry = entry if isinstance(entry, dict) else {}
        if eid is not None:
            entry[id_key] = eid
        aggs = edef.get("aggs") if isinstance(edef.get("aggs"), dict) else None
        if aggs is None and isinstance(edef.get("agg"), dict):
            aggs = {edef.get("value_key") or "value": edef["agg"]}
        computed = {}
        for k, aspec in (aggs or {}).items():
            if isinstance(aspec, dict):
                computed[k] = _reducers.reduce(aspec, els, computed=computed, context=_context_vals(state),
                                               element_spec=element_spec, policy=state["policy"])
                entry[k] = computed[k]
        rebuilt.append(entry)
    for container, key, _marker in _targets(payload, default_payload, slot):
        container[key] = copy.deepcopy(rebuilt)


# the slot MODES this module serves — roster.py's dispatch DISCOVERS this declaration from every roster_modes_* sibling
# (self-registration): a NEW mode = a new roster_modes_<x>.py declaring MODES, no dispatch edit.
MODES = {"aggregates": _aggregates_slot, "scalar": _scalar_slot, "entries": _entries_slot}
