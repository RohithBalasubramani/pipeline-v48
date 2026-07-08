"""ems_exec/executor/scalar_tile_fill.py — POST-FILL rescue of an UNBOUND MEASURABLE LABEL-KEYED TILE. ONE concern,
ZERO card knowledge: a `{label|title, value}` tile whose VALUE stayed blank (no field emitted for it) but whose LABEL
names a raw electrical magnitude (voltage / current) that IS present-and-logged on the card's OWN asset table is filled
with the window reduction of that column.

WHY (DEFECT A, card 50 ups-battery-autonomy): the Battery-Health card carries a metrics[] tile array
  [{label:"Temperature",unit:"°C"}, {label:"Output Voltage",unit:"V"}, {label:"Output Current",unit:"A"}]
whose data lives under the neutral key `value` (the quantity is in the sibling `label`, not the key). Layer 2 emitted NO
field for any of them (fields=[]), so every tile false-blanked — even "Output Voltage", though voltage_avg is live
(238.66 V, 61 791 non-null rows). scalar_mean_fill can't help: it keys the quantity off the DICT KEY ('value' has no
quantity token) and needs a sibling FIELD binding the same column (there is none). This pass reads the quantity from the
tile's LABEL instead, resolves the raw column via the SAME measurable_resolve semantics, and fills from the window mean.

OVER-REACH-SAFE BY CONSTRUCTION: a tile is filled ONLY when (1) its value leaf is BLANK or the untouched numeric
placeholder AND was NOT written by a real fill (never overwrites a measured reading), (2) its LABEL resolves
(measurable_resolve) to a column of a RAW magnitude quantity — a THD/harmonic/distortion or battery/thermal label
resolves to [] (the quantity wall in measurable_resolve refuses it), and (3) that column is PRESENT AND LOGGED on the
asset table. So "Output Voltage"/"Output Current" fill from voltage_avg/current_avg, while "Temperature" / "State of
Charge" (no voltage/current column) keep their honest blank. Generic — no card ids, no key literals. [atomic; never raises]
"""
from __future__ import annotations

from ems_exec.data import neuract as _nx
from ems_exec.executor import measurable_resolve as _mr
from ems_exec.executor.verify import _verify
from ems_exec.renderers import _agg


def _blank_or_placeholder(v):
    """A tile value that carries NO real reading: None/'—'/'' — OR the untouched build placeholder 0.0 (Layer 2 strips a
    seed tile value to 0.0 and no field replaced it). A REAL measured value is protected by the written-path fence in
    apply(), so treating a surviving 0.0 here as fillable never clobbers a genuine zero reading."""
    if v is None or v == "—" or v == "":
        return True
    try:
        ph = float(_placeholder())
    except (TypeError, ValueError):
        ph = 0.0
    return isinstance(v, (int, float)) and not isinstance(v, bool) and float(v) == ph


def _placeholder():
    try:
        from config import quality_policy as _qp
        return _qp.txt("placeholder.scalar", "0")
    except Exception:
        return "0"


def _unit_quantity(unit):
    """The dimensional quantity a tile UNIT names (config.vocab unit_quantities; only feeds _verify's negative-power abs
    convention — voltage/current never need it, so None is harmless). Never raises."""
    try:
        from config.vocab import unit_quantity
        return unit_quantity(unit)
    except Exception:
        return None


def _label_of(node, lkeys):
    """The tile's quantity-naming label — the first non-empty string sibling whose key is a label key
    (config.vocab label_keys: label/title/name/…). None when the tile carries no naming label."""
    for k, v in node.items():
        if str(k).lower() in lkeys and isinstance(v, str) and v.strip():
            return v
    return None


def _value_keys_and_label_keys():
    try:
        from config.vocab import vocab
        lk = {str(k).lower() for k in (vocab("label_keys") or ())}
        vk = {str(k).lower() for k in (vocab("value_keys") or ())}
        return lk, vk
    except Exception:
        return ({"label", "title", "name"}, {"value", "val"})


def apply(out, asset_table, window, written_value_paths=None, honest_blank_paths=None):
    """Fill every BLANK measurable LABEL-KEYED tile of `out` from its label's raw magnitude column window mean. Returns
    the set of leaf paths (dotted) filled REAL so the caller exempts them from the unbound-gap scan. No-op / empty set
    on any failure — telemetry-safe, never raises.

    `honest_blank_paths` (optional) = the AI's EXPLICIT honest-blank path-set (tokens-tuples from
    fill._honest_blank_paths). A tile whose value-leaf path (or the tile object's own path) is in this set is SKIPPED —
    the AI deliberately honest-blanked that leaf and a mechanical LABEL→column rescue must never resurrect it (DEFECT 56:
    'Average Bypass Voltage' ← voltage_avg over an explicit no-bypass-column honest-blank)."""
    filled = set()
    if not isinstance(out, dict) or not asset_table:
        return filled
    w = window or (None, None)
    lkeys, vkeys = _value_keys_and_label_keys()
    written = {tuple(_toks(p)) for p in (written_value_paths or ())}
    hb = honest_blank_paths or set()

    def _try_tile(node, path):
        label = _label_of(node, lkeys)
        if not label:
            return
        # the AI EXPLICITLY honest-blanked this tile (its object path OR any of its value leaves) → do NOT resurrect it.
        if _honest_blanked(path, hb):
            return
        unit = None
        ukeys = _mr.unit_keys()                                   # DB-driven unit-key vocab (measurable.unit_keys)
        for k, v in node.items():
            if str(k).lower() in ukeys and isinstance(v, str) and v.strip():
                unit = v
                break
        col = _mr.resolve_column(label, asset_table, unit=unit)   # RAW magnitude only (THD/battery/source-role → None)
        if not col:
            return                                                # no raw column measures this label → honest blank
        # find the blank value key(s) to fill on this tile
        for k, v in list(node.items()):
            if str(k).lower() not in vkeys:
                continue
            p = f"{path}.{k}" if path else str(k)
            if _honest_blanked(p, hb):
                continue                                          # this value leaf is an AI-declared honest-blank
            # A HARD blank (None/'—'/'') is UNAMBIGUOUSLY not a real reading, so it is always fillable — even when Layer 2
            # emitted a field for this slot that resolved to NO column (metric mismatch, e.g. 'runtime') and thereby
            # registered the path as 'written'. The written-path fence exists ONLY to protect a genuine 0.0 numeric reading
            # (indistinguishable from the stripped placeholder), so it applies solely to the numeric-placeholder case.
            hard_blank = v is None or v == "—" or v == ""
            if not hard_blank:
                if tuple(_toks(p)) in written or _under_written(p, written):
                    continue                                      # a real fill already wrote a number here — never overwrite
                if not _blank_or_placeholder(v):
                    continue
            series = _nx.bucketed(asset_table, col, w[0], w[1], sampling="hourly")
            vals = [pt.get("value") for pt in (series or []) if pt.get("value") is not None]
            if not vals:
                return                                            # no reading in the window → honest blank
            raw = sum(vals) / len(vals)
            val = _verify(_agg.num(raw), quantity=_unit_quantity(unit))
            if val is None:
                return
            node[k] = round(val, 1)
            filled.add(p)
            filled.add(f"data.{p}")

    def _walk(node, path):
        if isinstance(node, dict):
            # a tile = a dict carrying BOTH a label key and a value key
            has_label = any(str(k).lower() in lkeys and isinstance(v, str) and v.strip() for k, v in node.items())
            has_value = any(str(k).lower() in vkeys for k in node)
            if has_label and has_value:
                try:
                    _try_tile(node, path)
                except Exception:
                    pass
            for k, v in list(node.items()):
                if isinstance(k, str) and k.startswith("_"):
                    continue
                if isinstance(v, (dict, list)):
                    _walk(v, f"{path}.{k}" if path else str(k))
        elif isinstance(node, list):
            for i, el in enumerate(node):
                if isinstance(el, (dict, list)):
                    _walk(el, f"{path}[{i}]")

    _walk(out, "")
    return filled


def _toks(path):
    from ems_exec.executor.paths import _toks as _t
    return _t(path)


def _under_written(p, written):
    toks = tuple(_toks(p))
    return any(toks[:j] in written for j in range(1, len(toks) + 1))


def _honest_blanked(path, hb):
    """True when `path` (a tile object path OR a tile value-leaf path, dotted) matches a slot the AI EXPLICITLY
    honest-blanked. `hb` holds tokens-tuples normalized both address-ways by fill._honest_blank_paths; a '[*]' segment
    matches any index at that position. A match on the tile OBJECT path also blocks (an honest-blanked tile shouldn't be
    resurrected via a deeper value key)."""
    if not hb:
        return False
    toks = tuple(_toks(path))
    if not toks:
        return False
    if toks in hb:
        return True
    for entry in hb:
        if len(entry) == len(toks) and all(e == t or e == "*" for e, t in zip(entry, toks)):
            return True
    return False
