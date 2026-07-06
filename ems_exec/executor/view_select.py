"""ems_exec/executor/view_select.py — POST-FILL DEFAULT-VIEW SELECTION. One concern: a multi-view chart whose `view`
selector points at a view with NO data while a sibling view carries a REAL filled series opens on an empty chart with
the real data hidden behind the toggle (2026-07-06 card 48: view='v-thd' whose series=[] — V-THD unmeasured, honest —
while the real I-THD 25-pt series sat in views['i-thd']).

Shape-driven, NO card ids: any dict node carrying a STRING selector key whose value is a KEY OF a sibling `views`-like
dict (a dict-of-dicts the selector value indexes) is a view switch. When the SELECTED subtree carries no real data
leaf and another view's subtree does, the selector moves to the first data-bearing view (payload key order — a
deterministic, honest default). A subtree "carries real data" iff it holds ≥1 non-empty numeric array / series-of-
objects with a numeric leaf / finite scalar under a data-typed leaf (validate.leaf_classify — the ONE classifier).

apply(out) mutates in place and returns out. Valve: app_config view.auto_select ('on' unless 'off'). Never raises.
[atomic]
"""
from __future__ import annotations


def _enabled():
    try:
        from config.app_config import cfg
        return str(cfg("view.auto_select", "on")).strip().lower() != "off"
    except Exception:
        return True


def _has_real_data(subtree):
    """≥1 REAL data leaf in the subtree (leaf_classify data leaves, blanks excluded)."""
    try:
        from validate.leaf_classify import classify
        from ems_exec.executor.gaps import _blank_val
        from ems_exec.executor.paths import _leaf_at
        for d in classify(subtree).get("data_leaves") or []:
            v = _leaf_at(subtree, d.get("path"))
            if isinstance(v, list):
                if v and not all(x is None for x in v):
                    # a series-of-objects counts only when an element numeric leaf is non-blank
                    if all(isinstance(e, dict) for e in v):
                        if any(isinstance(x, (int, float)) and not isinstance(x, bool)
                               for e in v for x in e.values()):
                            return True
                    else:
                        return True
            elif not _blank_val(v):
                return True
    except Exception:
        return False
    return False


def apply(out):
    """Move every empty-view selector of `out` to its first data-bearing sibling view (in place). Never raises."""
    try:
        if _enabled() and isinstance(out, (dict, list)):
            _walk(out)
    except Exception:
        pass
    return out


def _walk(node):
    if isinstance(node, dict):
        for sel_key, sel in list(node.items()):
            if not (isinstance(sel, str) and sel):
                continue
            for views_key, views in node.items():
                if views_key == sel_key or not isinstance(views, dict):
                    continue
                if sel not in views or not isinstance(views.get(sel), dict):
                    continue                                     # the selector doesn't index this sibling dict
                if len([k for k, v in views.items() if isinstance(v, dict)]) < 2:
                    continue                                     # nothing to switch to
                if _has_real_data(views[sel]):
                    continue                                     # the chosen view already shows real data — honest
                target = next((k for k, v in views.items()
                               if k != sel and isinstance(v, dict) and _has_real_data(v)), None)
                if target is not None:
                    node[sel_key] = target                       # open on the view that HAS data (per-leaf honesty)
                break
        for v in node.values():
            if isinstance(v, (dict, list)):
                _walk(v)
    elif isinstance(node, list):
        for el in node:
            if isinstance(el, (dict, list)):
                _walk(el)
