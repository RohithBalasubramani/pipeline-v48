"""ems_exec/executor/roster_modes_sankey.py — the SANKEY roster mode: `sankey_match` re-values the design sankey's
nodes/links by slug-containment member match (member → its own read, trunk → the panel Σ, ungrounded entity →
honest-null); with `rebuild: true` the nodes/links (+ optional legend) are REBUILT from the real member roster instead
(the fixture's foreign entity labels never survive — the 2026-07-03 PCC-4 defect F). All vocabulary arrives in the
recipe rows — zero card knowledge. roster.py dispatches + re-exports byte-compatibly. [atomic]
"""
from __future__ import annotations

import copy

from ems_exec.executor import bindings as _bindings
from ems_exec.executor.roster_paths import _targets
from ems_exec.executor.roster_template import _default_at, _default_list_at, _merge_template, _merge_templates
from ems_exec.executor.roster_eval import _select, _context_vals


# ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
#  RENDER-SAFETY: never ship a null-endpoint sankey link (2026-07-07 pg02 card-13 d3-sankey 'missing: —' crash)
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
# d3-sankey's computeNodeLinks() resolves every link's {source,target} to a node by id via find(); an unresolvable id
# (null / the honest-blank '—' sentinel / an id no node carries) throws 'missing: <id>' and crashes the WHOLE card — NOT
# the per-leaf degrade contract. The roster builder writes RESOLVABLE endpoints, but a LATER post-fill class killer blanks
# a link's source/target string when it byte-matches the default's structural stage id (a sankey endpoint IS topology
# identity, byte-identical by design — but it collides with the narrative `source` key that class polices). So by the time
# the payload ships, EVERY endpoint can be null while the node roster (real ids + values) and each link's own value are
# intact.  Two-part guard:
#   1. the builder STASHES each link's resolvable {source,target} on the sankey under a reserved `_endpoints` key — a
#      leading-underscore key that the seed-leak / fab-guard passes skip by contract, so it survives fill() untouched;
#   2. _prune_dark_edges RESTORES a blanked endpoint from that stash (recovering the REAL member flow edge), THEN drops
#      any link still unresolved (a genuinely dark node has no edge), omits any now-edge-less node, and removes the stash.
# Generic (zero card ids) — applies to any flow/sankey. Per-leaf degrade: live member flows stay; only dark edges vanish.

_STASH_KEY = "_endpoints"                                      # reserved (leading '_') → skipped by the seed-leak passes


def _blank_ids():
    """The endpoint sentinels that never resolve to a node — a cmd_catalog vocab row with the code default. The FE's
    honest-blank sentinel is the em-dash '—' (== CMD_V2 fmtMetric METRIC_PLACEHOLDER); None/'' are the raw dark forms."""
    default = [None, "—", ""]
    try:
        from config.app_config import cfg
        v = cfg("roster.sankey.dark_endpoint_sentinels", None)
        if isinstance(v, list) and v:
            return set(v) | {None}
    except Exception:
        pass
    return set(default)


def _stash_endpoints(sankey):
    """Record each link's resolvable {source,target} (in link order) under the reserved `_endpoints` key so a later pass
    that blanks an endpoint string can be UNDONE at serve time. Called by the builder after it writes clean links."""
    if not isinstance(sankey, dict) or not isinstance(sankey.get("links"), list):
        return
    sankey[_STASH_KEY] = [{"source": lk.get("source"), "target": lk.get("target")}
                          if isinstance(lk, dict) else None for lk in sankey["links"]]


def _prune_dark_edges(sankey):
    """Restore any blanked link endpoint from the `_endpoints` stash, then drop every link still unresolved (null / '—' /
    not-a-real-node source OR target) so d3-sankey.find() never throws, omit any node left edge-less, and remove the
    stash. Per-leaf degrade: the live member flows stay, only edges to dark endpoints vanish. NEVER ships a null-endpoint
    link. In-place; no-op on a non-dict / listless sankey."""
    if not isinstance(sankey, dict):
        return
    nodes = sankey.get("nodes") if isinstance(sankey.get("nodes"), list) else None
    links = sankey.get("links") if isinstance(sankey.get("links"), list) else None
    if links is None:
        sankey.pop(_STASH_KEY, None)
        return
    blank = _blank_ids()
    node_ids = {n.get("id") for n in nodes if isinstance(n, dict)} if nodes is not None else None
    stash = sankey.get(_STASH_KEY) if isinstance(sankey.get(_STASH_KEY), list) else None

    def _resolvable(endpoint):
        if endpoint in blank:
            return False
        if node_ids is not None and endpoint not in node_ids:
            return False                                        # an id no node carries — d3-sankey.find() would throw
        return True

    # (1) RESTORE a blanked endpoint from the stash when the stashed id still names a real node (recover the real edge).
    if stash is not None:
        for i, lk in enumerate(links):
            if not isinstance(lk, dict) or i >= len(stash) or not isinstance(stash[i], dict):
                continue
            for end in ("source", "target"):
                if lk.get(end) in blank and _resolvable(stash[i].get(end)):
                    lk[end] = stash[i][end]

    # (2) DROP any link still unresolved; d3-sankey only ever sees resolvable endpoints.
    kept = [lk for lk in links
            if isinstance(lk, dict) and _resolvable(lk.get("source")) and _resolvable(lk.get("target"))]
    sankey["links"] = kept
    if nodes is not None:                                       # omit a node no surviving edge touches (a dark island)
        touched = {lk.get("source") for lk in kept} | {lk.get("target") for lk in kept}
        sankey["nodes"] = [n for n in nodes if not isinstance(n, dict) or n.get("id") in touched]
    sankey.pop(_STASH_KEY, None)                                # the stash is internal — never ships


def _sankey_slot(payload, spec, state, default_payload):
    if spec.get("rebuild"):
        _sankey_rebuild(payload, spec, state, default_payload)   # real-roster topology, never the foreign skeleton
        return
    targets = _targets(payload, default_payload, spec.get("slot"))
    if not targets:
        return
    container, key, _marker = targets[0]
    sankey = container.get(key)
    dflt = _default_at(default_payload, spec.get("slot"))
    if not isinstance(sankey, dict) and isinstance(dflt, dict):
        container[key] = copy.deepcopy(dflt)                    # design topology chrome; every VALUE overwritten below
        sankey = container[key]
    if not isinstance(sankey, dict):
        return
    if isinstance(dflt, dict):
        for part in ("nodes", "links"):
            if not sankey.get(part) and isinstance(dflt.get(part), list) and dflt.get(part):
                sankey[part] = copy.deepcopy(dflt[part])

    pairs = state["pairs"]
    by_slug = {_bindings.slugify(m.get("name")): (m, r) for (m, r) in pairs if m.get("name")}
    kind = (spec.get("default_value_kind") or "energy").strip().lower()
    member_binding = (spec.get("member_value") or {}).get(kind)
    trunk_name = spec.get("trunk_value")
    ctxv = _context_vals(state)
    trunk_v = ctxv.get(trunk_name) if trunk_name else None
    entity_v = spec.get("entity_value")
    marker_kinds = {str(k).strip().lower() for k in ((spec.get("trunk_markers") or {}).get("kinds") or [])}
    panel_self = bool((spec.get("trunk_markers") or {}).get("panel_self", True))
    panel_slugs = state["panel_slugs"] if panel_self else frozenset()

    def _member_value(mr):
        m, r = mr
        return _bindings.evaluate(member_binding, m, r, state["window"], state["policy"], ts_col=state["ts_col"])

    nodes = sankey.get("nodes") if isinstance(sankey.get("nodes"), list) else []
    roles = {}
    for n in nodes:
        if not isinstance(n, dict):
            continue
        role, mr = _node_role(n, by_slug, panel_slugs, marker_kinds)
        if n.get("id") is not None:
            roles[n["id"]] = (role, mr)
        if role == "member":
            n["value"] = _member_value(mr)
        elif role == "trunk":
            n["value"] = trunk_v
        else:
            n["value"] = entity_v                               # ungrounded entity → honest-null, never a duplicated Σ

    links = sankey.get("links")
    if isinstance(links, list) and (spec.get("link_match") or "by_node_id") == "by_node_id":
        for lk in links:
            if not isinstance(lk, dict):
                continue
            s_role, s_mr = roles.get(lk.get("source"), ("entity", None))
            t_role, t_mr = roles.get(lk.get("target"), ("entity", None))
            mr = (s_mr if s_role == "member" else None) or (t_mr if t_role == "member" else None)
            if mr is not None:
                lk["value"] = _member_value(mr)                 # the member's own flow (honest-null when dark)
            elif s_role == "trunk" and t_role == "trunk":
                lk["value"] = trunk_v                           # the panel's own trunk ribbon
            else:
                lk["value"] = entity_v

    _prune_dark_edges(sankey)                                   # never ship a null-endpoint link (d3-sankey.find crash)
    _stash_endpoints(sankey)                                   # survive a later endpoint-blanking pass (serve restores)


def _node_role(node, by_slug, panel_slugs, marker_kinds):
    """('member', (m,row)) | ('trunk', None) | ('entity', None) — slug-containment member match first, then the
    panel's own slug, then the declared trunk marker kind. Entity = a labelled node no member grounds."""
    label, nid = node.get("label"), node.get("id")
    mr = _match_slug(label, by_slug) or _match_slug(nid, by_slug)
    if mr is not None:
        return "member", mr
    for s in (_bindings.slugify(label), _bindings.slugify(nid)):
        if s and any(s in p or p in s for p in panel_slugs):
            return "trunk", None
    if str(node.get("kind") or "").strip().lower() in marker_kinds:
        return "trunk", None
    return "entity", None


def _match_slug(label, by_slug):
    s = _bindings.slugify(label)
    if not s:
        return None
    if s in by_slug:
        return by_slug[s]
    for k, v in by_slug.items():
        if k and (k in s or s in k):
            return v
    return None


# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#  sankey REBUILD — the real-roster topology (2026-07-03 PCC-4 defect F)
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
def _sankey_rebuild(payload, spec, state, default_payload):
    """REBUILD the sankey's nodes/links (+ optional legend) from the REAL member roster instead of re-valuing the
    design skeleton — the default's topology labels are another plant's entities (the PCC-1 'Incomer-1 (TF-01)' /
    UPS-01… / 'UPS backed loads' fixture) and re-valuing them fabricates a FOREIGN topology under honest-null values.
    Vocabulary (ALL from the recipe row — zero card knowledge here):
        member_value / default_value_kind   the per-member value binding (same closed set as sankey_match)
        trunk_value                          the run-level context value the trunk stages carry (e.g. panel_kwh)
        id_prefixes {supply, load}           the node-id prefixes the card's own selection helpers compose
        trunk_title_key                      the stage-node key that shows the panel's REAL display name (1st stage)
        trunk_markers.kinds                  which DEFAULT node kinds are trunk STAGES (chrome carried over, re-valued)
        legend {slot, groups:[{role, label, by?}]}  optional legend rebuild — by:'load_group' folds one item per
                                             registry load_group; else one item per member. Empty groups are dropped.
    Chrome (kinds / layers / colors) is inherited from the DEFAULT sankey's own nodes PER KIND — design-system chrome
    only, NEVER entity labels. Values per-leaf honest-null (a dark member stays null, never the duplicated panel Σ)."""
    targets = _targets(payload, default_payload, spec.get("slot"))
    if not targets:
        return
    container, key, _marker = targets[0]
    dflt = _default_at(default_payload, spec.get("slot"))
    dflt = dflt if isinstance(dflt, dict) else {}
    dnodes = [n for n in (dflt.get("nodes") or []) if isinstance(n, dict)]
    marker_kinds = {str(k).strip().lower() for k in ((spec.get("trunk_markers") or {}).get("kinds") or ["stage"])}

    kind_v = (spec.get("default_value_kind") or "energy").strip().lower()
    member_binding = (spec.get("member_value") or {}).get(kind_v)
    ctxv = _context_vals(state)
    trunk_v = ctxv.get(spec.get("trunk_value")) if spec.get("trunk_value") else None

    def _mval(m, r):
        return _bindings.evaluate(member_binding, m, r, state["window"], state["policy"], ts_col=state["ts_col"])

    def _mslug(m):
        return _bindings.slugify(m.get("name")) or str(m.get("mfm_id"))

    # per-kind chrome exemplars from the DEFAULT skeleton (kind → min layer + its ordered distinct colors)
    layer_of, colors_of = {}, {}
    for n in dnodes:
        knd = str(n.get("kind") or "").strip().lower()
        lyr = n.get("layer")
        if isinstance(lyr, (int, float)) and (knd not in layer_of or lyr < layer_of[knd]):
            layer_of[knd] = int(lyr)
        c = n.get("color")
        if c and c not in colors_of.setdefault(knd, []):
            colors_of[knd].append(c)
    stage_nodes = [copy.deepcopy(n) for n in dnodes if str(n.get("kind") or "").strip().lower() in marker_kinds]
    non_marker = [k for k in layer_of if k not in marker_kinds]
    max_stage = max((layer_of[str(n.get("kind") or "").strip().lower()] for n in stage_nodes
                     if str(n.get("kind") or "").strip().lower() in layer_of), default=0)
    supply_kind = min((k for k in non_marker), key=lambda k: layer_of[k], default="source")
    load_after = [k for k in non_marker if layer_of[k] > max_stage]
    load_kind = min(load_after, key=lambda k: layer_of[k], default=None) or "meter"
    prefixes = spec.get("id_prefixes") or {}
    sup_pre, load_pre = str(prefixes.get("supply") or ""), str(prefixes.get("load") or "")

    supply = _select(spec, state, role_filter="supply", reporting_only=False)
    load = _select(spec, state, role_filter="load", reporting_only=bool(spec.get("reporting_only")))

    # ── nodes ──────────────────────────────────────────────────────────────────────────────────────────────────────
    nodes, sup_ids, load_ids = [], [], []
    sup_colors = colors_of.get(supply_kind) or [None]
    for i, (m, r) in enumerate(supply):
        nid = sup_pre + _mslug(m)
        sup_ids.append((nid, _mval(m, r), sup_colors[i % len(sup_colors)]))
        node = {"id": nid, "kind": supply_kind, "label": m.get("name"), "layer": layer_of.get(supply_kind, 0),
                "value": sup_ids[-1][1]}
        if sup_ids[-1][2]:
            node["color"] = sup_ids[-1][2]
        nodes.append(node)
    if not stage_nodes:                                        # a skeleton with no stage → ONE trunk node keeps flow
        stage_nodes = [{"id": "panel", "kind": next(iter(marker_kinds), "stage"), "label": "",
                        "layer": layer_of.get(supply_kind, 0) + 1}]
    title_key = spec.get("trunk_title_key")
    panel_name = ctxv.get("panel_name")
    for j, n in enumerate(stage_nodes):
        n["value"] = trunk_v
        if j == 0 and title_key and panel_name:
            n[title_key] = str(panel_name)                     # the run's REAL panel identity, never a fixture title
    nodes.extend(stage_nodes)
    load_colors = colors_of.get(load_kind) or [None]
    groups_order, group_color = [], {}
    for m, _r in load:
        g = m.get("load_group") or "member"
        if g not in group_color:
            group_color[g] = load_colors[len(groups_order) % len(load_colors)]
            groups_order.append(g)
    load_layer = layer_of.get(load_kind, (max((n.get("layer") or 0) for n in stage_nodes) + 1))
    for m, r in load:
        nid = load_pre + _mslug(m)
        v = _mval(m, r)
        c = group_color.get(m.get("load_group") or "member")
        load_ids.append((nid, v, c))
        node = {"id": nid, "kind": load_kind, "label": m.get("name"), "layer": load_layer, "value": v}
        if c:
            node["color"] = c
        nodes.append(node)

    # ── links (supply → stage₀ → … → stageₙ → each load) ───────────────────────────────────────────────────────────
    links = []
    first_stage, last_stage = stage_nodes[0].get("id"), stage_nodes[-1].get("id")
    for nid, v, c in sup_ids:
        lk = {"source": nid, "target": first_stage, "value": v}
        if c:
            lk["color"] = c
        links.append(lk)
    for a, b in zip(stage_nodes, stage_nodes[1:]):
        lk = {"source": a.get("id"), "target": b.get("id"), "value": trunk_v}
        if a.get("color"):
            lk["color"] = a.get("color")
        links.append(lk)
    for nid, v, c in load_ids:
        lk = {"source": last_stage, "target": nid, "value": v}
        if c:
            lk["color"] = c
        links.append(lk)

    sankey = container.get(key) if isinstance(container.get(key), dict) else {}
    # per-element chrome fidelity: every rebuilt node/link clones its INDEX-MATCHED default counterpart's chrome
    # (curveSag, colors, kind extras — byte-faithful via the template rule) under the rebuilt values.
    sankey["nodes"] = _merge_templates(nodes, dflt.get("nodes"))
    sankey["links"] = _merge_templates(links, dflt.get("links"))
    _prune_dark_edges(sankey)                                   # never ship a null-endpoint link (d3-sankey.find crash)
    _stash_endpoints(sankey)                                   # survive a later endpoint-blanking pass (serve restores)
    container[key] = sankey

    # ── legend (optional; recipe-declared groups over the SAME real roster) ────────────────────────────────────────
    leg = spec.get("legend")
    if isinstance(leg, dict) and leg.get("slot"):
        dleg = _default_list_at(default_payload, leg.get("slot"))
        out_groups = []
        for g in (leg.get("groups") or []):
            if not isinstance(g, dict):
                continue
            role = (g.get("role") or "").strip().lower()
            if role == "supply":
                items = [{"color": c, "label": m.get("name")} for (m, _r), (_nid, _v, c) in zip(supply, sup_ids)]
            elif (g.get("by") or "").strip().lower() == "load_group":
                items = [{"color": group_color[grp], "label": str(grp)} for grp in groups_order]
            else:
                items = [{"color": c, "label": m.get("name")} for (m, _r), (_nid, _v, c) in zip(load, load_ids)]
            if items:
                gi = len(out_groups)
                dgrp = dleg[gi] if gi < len(dleg) and isinstance(dleg[gi], dict) \
                    else next((d for d in dleg if isinstance(d, dict)), None)
                group = _merge_template({"label": g.get("label"), "items": items}, dleg, gi)
                group["items"] = _merge_templates(items, (dgrp or {}).get("items"))
                out_groups.append(group)
        for lcontainer, lkey, _lm in _targets(payload, default_payload, leg.get("slot")):
            lcontainer[lkey] = copy.deepcopy(out_groups)       # wholesale — no foreign fixture legend survives
