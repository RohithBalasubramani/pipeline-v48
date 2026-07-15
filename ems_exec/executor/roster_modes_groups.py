"""ems_exec/executor/roster_modes_groups.py — the MEMBER-LIST roster modes: `elements` (one element per member →
role-filter → order → cap), `groups` (one chrome-templated group per member with its own element + group_agg) and
`sections` (members grouped per the recipe's section vocabulary with Σ section_agg totals). All vocabulary arrives in
the recipe rows — zero card knowledge. roster.py dispatches + re-exports byte-compatibly. [atomic]
"""
from __future__ import annotations

import copy

from ems_exec.executor import bindings as _bindings
from ems_exec.executor import reducers as _reducers
from ems_exec.executor.match_bounds import enabled, prefix_bounded
from ems_exec.executor.roster_paths import _targets
from ems_exec.executor.roster_template import _seedfree, _default_at, _default_list_at, _merge_template, _merge_templates
from ems_exec.executor.roster_eval import (
    _cfg, _select, _slot_window, _eval_elements, _order_cap, _context_vals)


def _elements_slot(payload, spec, state, default_payload):
    mels = _order_cap(_eval_elements(spec.get("element") or {}, _select(spec, state), state,
                                     window=_slot_window(spec, state)), spec)
    els = _merge_templates([e for (_m, e) in mels], _default_list_at(default_payload, spec.get("slot")))
    targets = _targets(payload, default_payload, spec.get("slot"))
    for n, (container, key, _marker) in enumerate(targets):
        container[key] = copy.deepcopy(els) if len(targets) > 1 or n > 0 else els


def _groups_slot(payload, spec, state, default_payload):
    slot = spec.get("slot")
    list_key = spec.get("list_key")
    targets = _targets(payload, default_payload, slot)
    if not targets or not list_key:
        return
    container, key, _marker = targets[0]
    existing = container.get(key) if isinstance(container.get(key), list) else []
    dlist = _default_list_at(default_payload, slot)
    fallback = next((g for g in list(dlist) + list(existing) if isinstance(g, dict)), None)
    if fallback is None:
        return                                                  # no chrome shape to clone → leave untouched (honest)
    rebuilt = []
    for n, (m, row) in enumerate(_select(spec, state)):
        # per-element chrome fidelity: the INDEX-MATCHED default group is this group's template (element[0]/the first
        # existing group when the counts differ) — its chrome survives byte-faithful, its list_key list templates the
        # rebuilt member elements, and only the recipe-bound keys below overwrite.
        t = dlist[n] if n < len(dlist) and isinstance(dlist[n], dict) else fallback
        g = _seedfree(t) or copy.deepcopy(t)
        for k, b in (spec.get("group") or {}).items():
            g[k] = _bindings.evaluate(b, m, row, state["window"], state["policy"], ts_col=state["ts_col"])
        el = _bindings.element(spec.get("element") or {}, m, row, state["window"], state["policy"],
                               ts_col=state["ts_col"])
        g[list_key] = _merge_templates([el], t.get(list_key))
        computed = {}
        for k, aspec in (spec.get("group_agg") or {}).items():
            # reducers fold the RAW bound element only — a template placeholder must never enter an aggregate
            computed[k] = _reducers.reduce(aspec, [el], computed=computed, context=_context_vals(state),
                                           element_spec=spec.get("element"), policy=state["policy"])
            g[k] = computed[k]
        rebuilt.append(g)
    container[key] = rebuilt


def _sections_slot(payload, spec, state, default_payload):
    """Members grouped per the recipe's section vocabulary. Two output shapes, both recipe-declared:
      · wrap_sample true (default) — the sections wrapped in ONE real sample [{…sample bindings, sections_key: […]}]
        (the heatmap history shape); wholesale replace.
      · wrap_sample false — the BARE section-entry list at the slot (a per-group aggregate roster, e.g. a supply
        breakdown: one entry per group with its Σ totals).
    Entry vocabulary (all from the recipe row): `elements_key` (optional — omitted → entries carry NO member list,
    aggregate-only), `section_agg` reducers, `entry` (consts merged into every entry, e.g. unit), `entry_palette`
    ({key, values} — values cycled per entry index, presentation chrome only)."""
    pairs = _select(spec, state)
    # recipe vocabulary `incomers_included`: the SUPPLY-side members always appear (dark or not — real entities with
    # honest-null numbers, per-leaf degradation), even when `reporting_only` filters the load side [PCC-4 defect fix].
    if spec.get("incomers_included"):
        seen = {m.get("mfm_id") for m, _r in pairs}
        pairs = pairs + [(m, r) for m, r in _select(spec, state, role_filter="supply", reporting_only=False)
                         if m.get("mfm_id") not in seen]
    grouped, order = _group_pairs(pairs, spec)
    elements_key = spec.get("elements_key")
    entry_consts = spec.get("entry") if isinstance(spec.get("entry"), dict) else {}
    palette = spec.get("entry_palette") if isinstance(spec.get("entry_palette"), dict) else {}
    pal_key, pal_vals = palette.get("key"), palette.get("values") or []
    sections_key = spec.get("sections_key") or _cfg("roster.sections_key_default", "sections")
    # the DEFAULT sections list (chrome templates): the bare list at the slot, or the wrapped sample's sections
    dflt = _default_at(default_payload, spec.get("slot"))
    if spec.get("wrap_sample") is False:
        dsecs = dflt if isinstance(dflt, list) else []
        dsample = None
    else:
        dsample = next((s for s in (dflt or []) if isinstance(s, dict)), None) if isinstance(dflt, list) else None
        dsecs = (dsample or {}).get(sections_key)
        dsecs = dsecs if isinstance(dsecs, list) else []
    sections = []
    for n, gid in enumerate(order):
        label, gpairs = grouped[gid]
        mels = _eval_elements(spec.get("element") or {}, gpairs, state)
        section = {"id": gid, "label": label}
        dsec = dsecs[n] if n < len(dsecs) and isinstance(dsecs[n], dict) \
            else next((s for s in dsecs if isinstance(s, dict)), None)
        if elements_key:
            section[elements_key] = _merge_templates([e for (_m, e) in mels], (dsec or {}).get(elements_key))
        for k, v in entry_consts.items():
            section[k] = copy.deepcopy(v)
        if pal_key and pal_vals:
            section[pal_key] = pal_vals[n % len(pal_vals)]
        computed = {}
        for k, aspec in (spec.get("section_agg") or {}).items():
            # reducers fold the RAW bound elements only — a template placeholder must never enter an aggregate
            computed[k] = _reducers.reduce(aspec, [e for (_m, e) in mels], computed=computed,
                                           context=_context_vals(state), element_spec=spec.get("element"),
                                           policy=state["policy"])
            section[k] = computed[k]
        sections.append(_merge_template(section, dsecs, n))     # entry chrome the recipe does not bind survives
    if spec.get("wrap_sample") is False:
        for container, key, _marker in _targets(payload, default_payload, spec.get("slot")):
            container[key] = copy.deepcopy(sections) if sections else []   # bare per-group roster; wholesale replace
        return
    sample = {}
    for k, b in (spec.get("sample") or {}).items():             # e.g. label = the NEWEST real row timestamp
        vals = [v for v in (_bindings.evaluate(b, m, r, state["window"], state["policy"], ts_col=state["ts_col"])
                            for m, r in pairs) if v is not None]
        sample[k] = max(vals) if vals else None
    sample[sections_key] = sections
    value = [_merge_template(sample, [dsample], 0)] if pairs else []       # sample-level chrome survives too
    for container, key, _marker in _targets(payload, default_payload, spec.get("slot")):
        container[key] = value                                  # wholesale replace — never a surviving seed sample


def _group_pairs(pairs, spec):
    """({group_id: (label, pairs)}, ordered_ids) per the recipe's section vocabulary. `section_defs` groups match by
    role / type / load_group / name-prefix (declaration order, incomers group included); unmatched members DERIVE a
    section from their own registry facts (policy-labelled field, e.g. load_group) — grouped, never dropped.
    Plain `group_by:'role'` groups by the registry edge role."""
    group_by = (spec.get("group_by") or "role").strip().lower()
    grouped, order = {}, []

    def _put(gid, label, pair):
        if gid not in grouped:
            grouped[gid] = (label, [])
            order.append(gid)
        grouped[gid][1].append(pair)

    if group_by == "section_defs":
        defs = [d for d in (spec.get("section_defs") or []) if isinstance(d, dict)]
        unmatched = spec.get("unmatched") or {}
        label_attr = unmatched.get("label") or "load_group"
        # seed the declared order so defined sections always precede derived ones
        for d in defs:
            gid = d.get("id")
            if gid is not None:
                grouped[gid] = (d.get("label"), [])
                order.append(gid)
        for m, r in pairs:
            d = _match_def(m, defs)
            if d is not None:
                grouped[d.get("id")][1].append((m, r))
                continue
            src = m.get(label_attr) or m.get("role") or "member"
            _put(_bindings.slugify(src), str(src), (m, r))
        # drop declared sections that matched nobody (honest — no empty design-fiction section)
        order = [gid for gid in order if grouped[gid][1]]
        grouped = {gid: grouped[gid] for gid in order}
        return grouped, order

    # group_by == 'role' (default): one section per registry edge role, deterministic sort (legacy behavior)
    for m, r in pairs:
        role = (m.get("role") or "member").strip().lower()
        _put(_bindings.slugify(role), role.title(), (m, r))
    order = sorted(order)
    return grouped, order


def _match_def(member, defs):
    """The FIRST section_def a member matches — by role, type, load_group, or name prefix (all vocabulary from the
    recipe row; comparisons case-insensitive). None → the member derives its own section."""
    role = str(member.get("role") or "").strip().lower()
    mtype = str(member.get("type") or "").strip().lower()
    lg = str(member.get("load_group") or "").strip().lower()
    fc = str(member.get("feeder_class") or "").strip().lower()
    name = str(member.get("name") or "").strip().lower()
    hardened = enabled()
    for d in defs:
        if role and role in {str(x).lower() for x in (d.get("roles") or [])}:
            return d
        if mtype and mtype in {str(x).lower() for x in (d.get("types") or [])}:
            return d
        if lg and lg in {str(x).lower() for x in (d.get("load_groups") or [])}:
            return d
        # T2.1-3: feeder_class fact any-of — the token-derived class (registry_feeder_class). No feeder_class /
        # no feeder_classes key on the def → this leg never fires (the member derives its own section as before).
        if fc and fc in {str(x).lower() for x in (d.get("feeder_classes") or [])}:
            return d
        # T2.1-2: name_prefixes is already left-anchored (startswith); when hardened, also require a right boundary
        # after the prefix (uniform with contains_bounded) so 'gic-2' no longer prefixes 'gic-20'. Flag off = verbatim.
        prefixes = d.get("name_prefixes") or []
        if name and (any(prefix_bounded(name, str(p).lower()) for p in prefixes) if hardened
                     else any(name.startswith(str(p).lower()) for p in prefixes)):
            return d
    return None


# the slot MODES this module serves — roster.py's dispatch DISCOVERS this declaration from every roster_modes_* sibling
# (self-registration): a NEW mode = a new roster_modes_<x>.py declaring MODES, no dispatch edit.
MODES = {"elements": _elements_slot, "groups": _groups_slot, "sections": _sections_slot}
