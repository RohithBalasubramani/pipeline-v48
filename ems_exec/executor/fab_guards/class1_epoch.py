"""fab_guards/class1_epoch.py — CLASS 1: an epoch-millisecond magnitude written into a NON-time leaf is a
timestamp leaked as a reading — blank it (time-axis keys exempt via the knobs vocab)."""
from __future__ import annotations

from ems_exec.executor.paths import _toks, _set_path
from ems_exec.executor.fab_guards.knobs import _epoch_floor, _is_num, _is_time_axis_key, _add_gap

def _is_epoch_scalar(v, floor):
    return _is_num(v) and v >= floor


def _is_epoch_array(v, floor):
    """Every numeric element is an epoch-ms magnitude (a non-empty, all-numeric, all-epoch array). None elements are
    ignored (an honest-blank point among timestamps), but at least one real epoch value must be present."""
    if not isinstance(v, list) or not v:
        return False
    nums = [x for x in v if x is not None]
    if not nums or any(not _is_num(x) for x in nums):
        return False
    return all(x >= floor for x in nums)


def _apply_class1(out, gaps):
    """CLASS 1 — recurse the FINISHED payload; wherever a NON-time-axis leaf (scalar OR all-numeric array) carries
    epoch-ms magnitudes, blank it. A time-axis key (…ticks/…indexes/…timestamps/ts/…) is exempt; series-of-OBJECTS are
    recursed per element so a mislabeled per-point value key (points[i].value ← ms) is caught while the point's own
    time key (points[i].time) is exempt. Two-pass: collect the paths (a stable recursion over `out`), then set each
    None/[] type-safely (a scalar → None; an all-epoch array → [] so the FE never .map()s a null)."""
    floor = _epoch_floor()
    to_null = []          # (path, is_array)

    def _walk(node, path, key):
        if isinstance(node, dict):
            for k, v in node.items():
                _walk(v, f"{path}.{k}" if path else str(k), k)
            return
        if isinstance(node, list):
            if not _is_time_axis_key(key) and _is_epoch_array(node, floor) \
                    and all(_is_num(x) or x is None for x in node):
                to_null.append((path, True))
                return
            for i, el in enumerate(node):
                _walk(el, f"{path}[{i}]", key)
            return
        if not _is_time_axis_key(key) and _is_epoch_scalar(node, floor):
            to_null.append((path, False))

    _walk(out, "", "")
    for path, is_arr in to_null:
        key = _toks(path)[-1] if _toks(path) else path
        _set_path(out, path, [] if is_arr else None)
        _add_gap(gaps, path, "epoch_ms_leak", key)
    return {p for p, _ in to_null}


# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#  CLASS 2 / CLASS 3 — per-WRITTEN-leaf source audit (needs the declared fields + the meter's present/logged columns).
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
