"""ems_exec/executor/paths.py — THE ONE dotted-path address home (dotted + indexed: a.b[0].c / a.b.0.c).

Single definition of payload-leaf addressing for the whole pipeline: the executor fill (fill.py re-exports these
byte-compatibly), the display reconcile (display._parent_of), the render verdict (validate.render_verdict._at_path)
and the grounding assembler (grounding.default_assemble._set_at/_get_at) all resolve paths HERE. Tokenizer =
re.findall(r"[^.\\[\\]]+"); descent = isdigit→int key; KeyError/IndexError/TypeError → None / no-op (honest).
[atomic; stdlib only]
"""
from __future__ import annotations

import re

_TOK = re.compile(r"[^.\[\]]+")


def _toks(path):
    return _TOK.findall(path or "")


def _leaf_at(tree, path):
    node = tree
    for t in _toks(path):
        key = int(t) if t.isdigit() else t
        try:
            node = node[key]
        except (KeyError, IndexError, TypeError):
            return None
    return node


def _set_path(tree, path, value):
    toks = _toks(path)
    if not toks:
        return
    node = tree
    for t in toks[:-1]:
        key = int(t) if t.isdigit() else t
        try:
            node = node[key]
        except (KeyError, IndexError, TypeError):
            return
    last = toks[-1]
    key = int(last) if last.isdigit() else last
    try:
        node[key] = value
    except (KeyError, IndexError, TypeError):
        return


def _has_path(tree, path):
    node = tree
    toks = _toks(path)
    if not toks:
        return False
    for t in toks:
        key = int(t) if t.isdigit() else t
        try:
            node = node[key]
        except (KeyError, IndexError, TypeError):
            return False
    return True


def _parent_of(tree, path):
    """The OBJECT that directly contains the leaf at `path` (its {value, displayValue, delta, …} reading object), or
    None. E.g. path 'data.readings.activePower.value' → the activePower dict."""
    toks = _toks(path)
    if len(toks) < 2:
        return None
    node = tree
    for t in toks[:-1]:
        key = int(t) if t.isdigit() else t
        try:
            node = node[key]
        except (KeyError, IndexError, TypeError):
            return None
    return node if isinstance(node, dict) else None


def _set_leaf_typed(tree, path, value):
    """Set a leaf but PRESERVE its container type: a None/scalar NEVER nulls an ARRAY (the FE .map()s it) or a dict.
    A real list replaces a list leaf; a real dict replaces a dict leaf; a scalar leaf becomes the real number OR None."""
    cur = _leaf_at(tree, path)
    if isinstance(cur, list):
        if isinstance(value, list):
            _set_path(tree, path, value)
        return
    if isinstance(cur, dict):
        if isinstance(value, dict):
            _set_path(tree, path, value)
        return
    _set_path(tree, path, value)


def _leaf_path_for(payload, slot):
    """The dotted leaf PATH a field binds to. CMD_V2 payloads nest data under `data.<slot>`; some carry it at top level
    or the field already gives a dotted path. Prefer data.<slot>, else <slot> (which also resolves a dotted path)."""
    if not slot:
        return None
    for cand in (f"data.{slot}", str(slot)):
        if _has_path(payload, cand):
            return cand
    return None
