"""ems_exec/executor/roster_paths.py — the ROSTER SLOT-PATH resolver: dotted path with [] (array target) and [*]
(repeat into every existing element), the data-envelope base pick, the sibling-shape suffix re-address, and BOTH
walks over that address form — the MUTATING _targets/_walk (grafts gate-elided spine containers seed-free, unwinds
still-empty debris) and the READ-ONLY values_at (roster_stats' telemetry mirror: never grafts, never creates a spine
node). ONE home for roster slot addressing. roster.py re-exports byte-compatibly. [atomic]
"""
from __future__ import annotations

import re

from ems_exec.executor.graft import _graft_seedfree

_TOK = re.compile(r"([^.\[\]]+)(\[\*\]|\[\])?")


def _toks(slot):
    return [(m.group(1), m.group(2) or "") for m in _TOK.finditer(slot or "")]


def _base(payload, default_payload, first):
    """The tree the slot path starts in: the payload root when it (or the default) carries the first token there, else
    the payload's `data` envelope when the token lives under it — mirroring fill._leaf_path_for's data.<slot> address."""
    dp = default_payload if isinstance(default_payload, dict) else {}
    if first in payload or first in dp:
        return payload, dp
    data = payload.get("data")
    if isinstance(data, dict) and (first in data or first in (dp.get("data") or {})):
        return data, dp.get("data") if isinstance(dp.get("data"), dict) else {}
    return payload, dp


def _readdress(payload, default_payload, toks):
    """SHAPE RE-ADDRESS [card-69 mis-addressed sibling stats]: a card_fill_recipe slot authored for a SIBLING card's
    payload shape (the endpoint-FAMILY recipe: 'history.data.stats.0.value' on the history-rooted card 46) does not
    fit a card whose OWN default roots at `data.*`. When the FULL slot path resolves in NEITHER the payload NOR the
    default, the LONGEST strictly-shorter SUFFIX that DOES fully resolve is this card's own address for the same leaf
    ('data.stats.0.value') — write THERE instead of manufacturing an alien string-keyed subtree the component never
    reads. Nothing resolves at any suffix → the ORIGINAL toks return (creation semantics preserved for
    build-from-scratch slots like widgets.sld.*). Read-only probe; never raises."""
    def _resolves(tk):
        bases = []
        for src in (payload, default_payload):
            if isinstance(src, dict):
                bases.append(src)
                if isinstance(src.get("data"), dict):
                    bases.append(src["data"])
        for base in bases:
            node, ok = base, True
            for name, marker in tk:
                if isinstance(node, list):
                    if name.lstrip("-").isdigit() and -len(node) <= int(name) < len(node):
                        node = node[int(name)]
                    else:
                        ok = False
                        break
                elif isinstance(node, dict) and name in node:
                    node = node[name]
                else:
                    ok = False
                    break
                if marker in ("[*]", "[]") and isinstance(node, list):
                    node = node[0] if node else None
            if ok:
                return True
        return False

    if _resolves(toks):
        return toks
    for k in range(1, len(toks)):
        if _resolves(toks[k:]):
            return toks[k:]
    return toks


def _targets(payload, default_payload, slot):
    """[(container, final_key, final_marker)] for a slot path — walks/creates the dict spine (grafting a gate-elided
    container back from the DEFAULT payload seed-free where it exists), fans out at `[*]` into every existing array
    element. Missing `[*]` arrays are grafted from the default; a path that cannot be resolved yields [] (honest skip,
    never a KeyError). A spine container CREATED during the walk is pruned again when the path ultimately resolved no
    target and the container stayed empty — a recipe slot that does not fit this payload's shape (e.g. a swapped card)
    must leave ZERO debris behind. A family-recipe slot rooted in a SIBLING card's shape is suffix-RE-ADDRESSED onto
    this payload's own leaf first (_readdress) — never an alien manufactured subtree."""
    toks = _toks(slot)
    if not toks:
        return []
    try:
        toks = _readdress(payload, default_payload, toks)
    except Exception:
        pass
    node, dnode = _base(payload, default_payload, toks[0][0])
    out = []
    created = []                                                # (container, key) spine nodes created by this walk
    _walk(node, dnode, toks, 0, out, created)
    if not out:
        for holder, key in reversed(created):                   # unwind: only still-empty debris is removed
            v = holder.get(key)
            if v == {} or v == []:
                del holder[key]
    return out


def _walk(node, dnode, toks, i, out, created):
    # numeric-INDEX descent into an existing list element (a FIXED-position array leaf, e.g. `stats.0.value` — a KPI
    # tile whose slot is a stable index, not a member-rebuilt row). Only an already-present index is addressed (never
    # grown/created): the tile array is design chrome the default already carries. dnode tracks the index-matched
    # default element so the child dict-walk keeps its template refs. Non-numeric token on a list / OOB → honest skip.
    if isinstance(node, dict):
        name, marker = toks[i]
    elif isinstance(node, list):
        idx_tok = toks[i][0]
        if not (isinstance(idx_tok, str) and idx_tok.lstrip("-").isdigit()):
            return
        idx = int(idx_tok)
        if not (-len(node) <= idx < len(node)):
            return
        dref = dnode[idx] if isinstance(dnode, list) and -len(dnode) <= idx < len(dnode) else None
        _walk(node[idx], dref, toks, i + 1, out, created)
        return
    else:
        return
    dchild = dnode.get(name) if isinstance(dnode, dict) else None
    if i == len(toks) - 1:
        out.append((node, name, marker))
        return
    child = node.get(name)
    if marker == "[*]":
        if not isinstance(child, list) or not child:
            graft = _graft_seedfree(dchild) if isinstance(dchild, list) else None
            if graft:
                node[name] = graft
                created.append((node, name))
                child = graft
        if not isinstance(child, list):
            return                                              # no array to repeat into → honest skip
        dlist = dchild if isinstance(dchild, list) else []
        for j, el in enumerate(child):
            if isinstance(el, dict):
                dref = dlist[j] if j < len(dlist) else (dlist[0] if dlist else None)
                _walk(el, dref, toks, i + 1, out, created)
        return
    if child is None or not isinstance(child, (dict, list)):
        graft = _graft_seedfree(dchild) if isinstance(dchild, (dict, list)) else None
        node[name] = graft if graft is not None else {}
        created.append((node, name))
        child = node[name]
    _walk(child, dchild, toks, i + 1, out, created)


# ── read-only slot-path resolution (the SAME addressing as _targets, but NEVER mutates — roster_stats' mirror) ───────
def values_at(payload, slot):
    """Every value the slot path resolves to on the COMPLETED payload — read-only: never grafts, never creates a spine
    node (telemetry must not alter the served payload). [*] fans into every existing dict element; a numeric token
    indexes an existing list element; anything unresolvable → []."""
    toks = _toks(slot)
    if not toks or not isinstance(payload, dict):
        return []
    node = payload
    first = toks[0][0]
    if first not in payload and isinstance(payload.get("data"), dict) and first in payload["data"]:
        node = payload["data"]
    frontier = [node]
    for name, marker in toks:
        nxt = []
        for n in frontier:
            if isinstance(n, list):
                # numeric-INDEX read into a fixed-position array element (mirrors _walk; read-only)
                if isinstance(name, str) and name.lstrip("-").isdigit() and -len(n) <= int(name) < len(n):
                    nxt.append(n[int(name)])
                continue
            if not isinstance(n, dict) or name not in n:
                continue
            child = n.get(name)
            if marker == "[*]":
                nxt.extend(el for el in (child if isinstance(child, list) else []) if isinstance(el, dict))
            else:
                nxt.append(child)
        frontier = nxt
        if not frontier:
            return []
    return frontier
