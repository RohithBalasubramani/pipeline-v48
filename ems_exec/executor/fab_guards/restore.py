"""fab_guards/restore.py — CHROME-RESTORE: a RESTORATION pass (not a blanking guard) fill.py invokes EARLY
(before view_select), re-instating blanked enum/selector/scale chrome from the default so the component keeps its
chrome shape. Shares the chrome vocab with class4_seed."""
from __future__ import annotations

from ems_exec.executor.paths import _set_path
from ems_exec.executor.fab_guards.knobs import _is_num
from ems_exec.executor.fab_guards.class4_seed import (_written_toks, _is_written, _chrome_selector_keys,
                                                      _is_chrome_key, _key_words)

_SCALE_SELECTOR_KEYS_DEFAULT = {"scalemaxpct", "limitpct", "scalemax", "defaultlimit"}


def _scale_selector_keys():
    """The chrome-selector keys whose BLANK is a degenerate 0/0.0 (a gauge SCALE/limit that can't draw a bar at
    zero-max) — a SUBSET of chrome_selector_keys, kept a separate row so a new scale key is added with no code change.
    DB knob fab_guards.scale_selector_keys (JSON list, lowercased) with the code-default mirror."""
    try:
        from config.app_config import cfg
        rows = cfg("fab_guards.scale_selector_keys", None)
        if rows:
            return {str(k).strip().lower() for k in rows}
    except Exception:
        pass
    return set(_SCALE_SELECTOR_KEYS_DEFAULT)


def _scale_selector_key(k):
    """A chrome-selector key whose BLANK is a degenerate 0/0.0 (a gauge SCALE/limit that can't draw a bar at zero-max),
    not a null/'' string selector. For these the restore treats a numeric 0 as blank; for a string selector/enum it
    does not (0 is not a selector value). Keyed off the DB-driven scale-key vocab (a subset of the selector vocab)."""
    return k in _scale_selector_keys()


def _chrome_is_blank(cur, key):
    """Is the current chrome leaf value BLANK (stripped) — a string selector/enum None/'' , OR a scale key at 0/0.0?
    A non-blank real chrome value (a live selector the fill legitimately set) is NEVER overwritten by the restore."""
    if cur is None or cur == "":
        return True
    if _scale_selector_key(key) and _is_num(cur) and float(cur) == 0.0:
        return True
    return False


def restore_chrome(out, default_payload, written=None):
    """Walk `out` and `default_payload` in parallel; wherever a leaf whose KEY is a chrome SELECTOR/enum/scale key
    (fab_guards._chrome_selector_keys) is BLANK in `out` (null/''/a zero scale) while the default holds a NON-blank
    value, RESTORE the default value. Over-reach-safe:
      • ONLY chrome-selector keys are touched (a genuine measurement/data key is never in the vocab → still honest-blanks);
      • a WRITTEN leaf (the fill set it real — in / under `written`) is left as-is (a live selector wins over the default);
      • the default value must itself be non-blank (never restores a null over a null — no fabrication).
    It descends every dict/list uniformly (a selector can sit inside a bottomStats/quickStats object list); the selector-
    key vocab is the ONLY wall — never a shape heuristic — so a `dir` nested in a stat-object list is reached, while a
    warn/trip threshold LINE (not in the vocab) is never touched.
    Mutates `out` in place; returns the set of restored token-tuples. Never raises (fail-open on the honest fill)."""
    if not isinstance(out, dict) or not isinstance(default_payload, dict):
        return set()
    wtoks = _written_toks(written)
    restored = set()

    def _walk(node, dflt, toks):
        if isinstance(node, dict):
            if not isinstance(dflt, dict):
                return
            for k, v in list(node.items()):
                if isinstance(k, str) and k.startswith("_"):
                    continue
                if k not in dflt:
                    continue
                kl = str(k).lower()
                if isinstance(v, (dict, list)):
                    _walk(v, dflt[k], toks + (str(k),))
                    continue
                if kl not in _chrome_selector_keys():
                    continue
                if not _chrome_is_blank(v, kl):
                    continue                                    # a live/real chrome value — never overwrite
                if _is_written(toks + (str(k),), wtoks):
                    continue                                    # the fill set this leaf real
                dv = dflt[k]
                if dv is None or dv == "" or isinstance(dv, (dict, list)):
                    continue                                    # nothing non-blank to restore (never null-over-null)
                _set_path(out, ".".join(str(t) for t in toks + (str(k),)), dv)
                restored.add(toks + (str(k),))
            return
        if isinstance(node, list):
            if isinstance(dflt, list):
                for i, el in enumerate(node):
                    if i < len(dflt):
                        _walk(el, dflt[i], toks + (str(i),))
            return

    try:
        _walk(out, default_payload, ())
    except Exception:
        return restored
    return restored


# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#  apply — the ONE post-fill guard entry wired into fill.py (after every honest fill pass).
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
