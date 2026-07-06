"""ems_exec/executor/roster_template.py — the TEMPLATE-CLONE rule (per-leaf + FE-contract, 2026-07-03 pages 02/03
chrome defect): every REBUILT roster element (sankey node/link, group, meter, section entry/member, series point)
CLONES its DEFAULT element TEMPLATE — the index-matched element of the default payload's list at the same slot
(element[0] when the counts differ) — through the canonical seed-strip, so per-element CHROME (curveSag, colors, kind,
stageTitle …) survives byte-faithful while unbound DATA keys reset to typed placeholders; ONLY the recipe-bound value
keys overwrite. Plus the default-payload subtree readers the templates come from. roster.py re-exports byte-compatibly.
[atomic]
"""
from __future__ import annotations

from ems_exec.executor.graft import _graft_seedfree
from ems_exec.executor.roster_paths import _toks, _base


def _seedfree(subtree):
    """A seed-free deep copy of a default subtree (typed placeholders only — chrome survives, numbers reset).
    Delegates to the executor's canonical graft; None when it cannot be stripped (honest refusal)."""
    return _graft_seedfree(subtree)


def _default_at(default_payload, slot):
    """The DEFAULT payload's subtree at a slot path (for chrome templates), or None."""
    if not isinstance(default_payload, dict):
        return None
    toks = _toks(slot)
    if not toks:
        return None
    node = _base(default_payload, None, toks[0][0])[0]
    for j, (name, marker) in enumerate(toks):
        if not isinstance(node, dict):
            return None
        node = node.get(name)
        if marker == "[*]" and isinstance(node, list):
            node = node[0] if node else None
    return node


def _default_list_at(default_payload, slot):
    """The DEFAULT payload's element LIST at a slot path, or [] (template source for rebuilt rosters)."""
    d = _default_at(default_payload, slot)
    return d if isinstance(d, list) else []


def _merge_template(el, dlist, i):
    """ONE rebuilt roster element CLONED over its DEFAULT element TEMPLATE (FE contract, per-leaf): the template is
    the INDEX-MATCHED default element — or the default's first element when the counts differ and the index runs past
    the default list — run through the canonical seed-strip so CHROME keys survive byte-faithful (curveSag, colors,
    kind, stageTitle — vocab.chrome_subtree_keys keeps chrome-numerics) while unbound DATA keys reset to their typed
    placeholders (never a seeded number); then ONLY the recipe-bound keys (the rebuilt element's own) overwrite.
    A rebuilt element therefore always carries EVERY key its default counterpart has — the component's element
    contract — losing none and fabricating none. Non-dict element / no usable template → the element unchanged."""
    if not isinstance(el, dict) or not isinstance(dlist, list) or not dlist:
        return el
    t = dlist[i] if i < len(dlist) and isinstance(dlist[i], dict) \
        else next((d for d in dlist if isinstance(d, dict)), None)
    if not isinstance(t, dict):
        return el
    base = _seedfree(t)
    if not isinstance(base, dict):
        return el
    base.update(el)
    return base


def _merge_templates(els, dlist):
    """Template-clone a whole rebuilt element list against the DEFAULT list at the same slot (index-matched)."""
    if not isinstance(dlist, list) or not dlist:
        return els
    return [_merge_template(e, dlist, i) for i, e in enumerate(els)]
