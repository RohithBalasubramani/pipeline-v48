"""ems_exec/executor/scalar_mean_fill.py — POST-FILL rescue of an UNBOUND MEASURABLE SCALAR-AVERAGE leaf. ONE concern,
ZERO card knowledge: a scalar payload leaf that names a reduced magnitude (…AvgKw / …MaxKw / …Min… — a quantity token +
a statistic token) but stayed BLANK because Layer 2 emitted NO field for it, yet a SIBLING data field on the SAME card
already binds a real neuract column of that quantity, is filled with the window reduction of that column.

WHY (R4 residual, card 40): the AI emitted data.bars[*].active (column active_power_total_kw, agg='avg') + bars[*].reactive
(reactive_power_total_kvar) but NO field for the scalar leaves data.activePowerAvgKw / data.reactivePowerAvgKw, so both
false-blanked '—' though the columns exist non-null live. The scalar is exactly the window-mean of the sibling series'
column — the SAME reduction the bars already show — so it fills deterministically here.

OVER-REACH-SAFE BY CONSTRUCTION: fires ONLY on a leaf that is (1) BLANK in the completed payload, (2) whose key resolves
(measurable_resolve) to a sibling field's real column of the same quantity, AND (3) that column is PRESENT AND LOGGED on
the asset table. A leaf with no matching sibling column, or a column that is absent/all-null, keeps its honest blank.
Generic — no card ids, no key literals; the column comes from the sibling emission + the DB. [atomic; never raises]
"""
from __future__ import annotations

from ems_exec.data import neuract as _nx
from ems_exec.executor import measurable_resolve as _mr
from ems_exec.executor.verify import _verify
from ems_exec.renderers import _agg


def _blank(v):
    return v is None or v == "—" or v == ""


def _honest_blanked(path, hb):
    """True when `path` (a dotted walk path) matches a slot the AI EXPLICITLY honest-blanked. `hb` holds tokens-tuples
    already normalized both address-ways (bare + data.<slot>) by fill._honest_blank_paths, so the bare-path tokens are
    matched directly. A wildcard '[*]' segment in the honest-blank set matches any index at that position."""
    if not hb:
        return False
    from ems_exec.executor.paths import _toks
    toks = tuple(_toks(path))
    if toks in hb:
        return True
    for entry in hb:
        if len(entry) == len(toks) and all(e == t or e == "*" for e, t in zip(entry, toks)):
            return True
    return False


def _has_stat_and_quantity(key):
    """True iff the leaf key names BOTH a magnitude quantity (voltage/current/power/…) and a per-sample STATISTIC
    (avg/max/min) — the shape of a reduced-scalar leaf (activePowerAvgKw / worstCurrentMaxA). Uses the shared tokenizer;
    a leaf naming only a quantity (no stat) or only chrome is skipped (never guessed)."""
    toks = set(_mr._tokens(key))
    stat = toks & set(_mr._stat_map().keys())
    # a quantity token: either a mapped electrical abbrev OR one of the generic magnitude words the sibling match keys on
    # (measurable.scalar_quantity_words — DB-driven vocab, ONE home in measurable_resolve; no hardcoded set here).
    quant = (toks & set(_mr._quantity_map().keys())) or (toks & _mr.scalar_quantity_words())
    return bool(stat and quant)


def apply(out, fields, asset_table, window, honest_blank_paths=None):
    """Fill every BLANK measurable-average scalar leaf of `out` from its sibling-emitted column's window reduction.
    Returns the set of leaf paths (dotted) this pass filled REAL (so the caller can exempt them from the unbound-gap
    scan / placeholder-null). No-op / empty set on any failure — telemetry-safe, never raises.

    `honest_blank_paths` (optional) = the AI's EXPLICIT honest-blank path-set (tokens-tuples from fill._honest_blank_paths).
    A leaf whose slot-path is in this set is SKIPPED — the AI deliberately honest-blanked it and a mechanical mean rescue
    must never resurrect it (DEFECT 56)."""
    filled = set()
    if not isinstance(out, dict) or not asset_table or not fields:
        return filled
    w = window or (None, None)
    hb = honest_blank_paths or set()

    def _walk(node, path):
        if isinstance(node, dict):
            for k, v in list(node.items()):
                if isinstance(k, str) and k.startswith("_"):
                    continue                                   # reserved telemetry (_roster_stats/_blank_gaps) — skip
                p = f"{path}.{k}" if path else str(k)
                if _blank(v) and _has_stat_and_quantity(k) and not _honest_blanked(p, hb):
                    try:
                        _try_fill(node, k, p)
                    except Exception:
                        pass
                elif isinstance(v, (dict, list)):
                    _walk(v, p)
        elif isinstance(node, list):
            for i, el in enumerate(node):
                if isinstance(el, (dict, list)):
                    _walk(el, f"{path}[{i}]")

    def _try_fill(container, key, path):
        col, quantity = _mr.sibling_column_for_scalar(key, fields)
        if not col or not _nx.column_logged(asset_table, col):
            return                                             # no real sibling column → honest blank stands
        toks = set(_mr._tokens(key))
        stat = next((s for t, s in _mr._stat_map().items() if t in toks), "avg")
        series = _nx.bucketed(asset_table, col, w[0], w[1], sampling="hourly")
        vals = [pt.get("value") for pt in (series or []) if pt.get("value") is not None]
        if not vals:
            return                                             # no real reading in the window → honest blank
        if stat == "max":
            raw = max(vals)
        elif stat == "min":
            raw = min(vals)
        else:
            raw = sum(vals) / len(vals)
        val = _verify(_agg.num(raw), quantity=quantity)        # denorm clamp + negative-power abs convention
        if val is None:
            return
        container[key] = round(val, 1)
        filled.add(path)
        filled.add(f"data.{path}")

    _walk(out, "")
    return filled
