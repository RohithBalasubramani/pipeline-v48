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


def _aggregates_slot(payload, spec, state, default_payload):
    element_spec = spec.get("element") if isinstance(spec.get("element"), dict) and spec.get("element") \
        else _shared_element(state)
    slot_rf = spec.get("role_filter") or "all"
    slot_ro = bool(spec.get("reporting_only"))
    slot_win = _slot_window(spec, state)
    cache = {}

    def _els(rf, ro):
        k = (rf, ro)
        if k not in cache:
            cache[k] = [e for (_m, e) in
                        _eval_elements(element_spec, _select(spec, state, role_filter=rf, reporting_only=ro), state,
                                       window=slot_win)]
        return cache[k]

    aggs = spec.get("agg") or {}
    computed = {}
    late = {}
    for k, aspec in aggs.items():
        if not isinstance(aspec, dict):
            continue
        if (aspec.get("agg") or "").strip().lower() in ("alias", "sum_of", "difference", "ratio_pct"):
            late[k] = aspec                                     # sibling-referencing reducers run after the rest
            continue
        rf = aspec.get("role_filter") or slot_rf
        computed[k] = _reducers.reduce(aspec, _els(rf, slot_ro), computed=computed,
                                       context=_context_vals(state), element_spec=element_spec,
                                       policy=state["policy"])
    for k, aspec in late.items():
        computed[k] = _reducers.reduce(aspec, [], computed=computed, context=_context_vals(state),
                                       element_spec=element_spec, policy=state["policy"])
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
