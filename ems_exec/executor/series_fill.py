"""ems_exec/executor/series_fill.py — series / time-axis fill: the bucketed history read (shape-aware object elements),
the series-element value/time key vocabulary, epoch conversion, time-field detection and the card's shared anchor
timestamp axis. One concern; fill.py re-exports byte-compatibly. [atomic]
"""
from __future__ import annotations

from ems_exec.data import neuract as _nx
from ems_exec.executor.verify import _verify


def _event_count(asset_table, col, window):
    """Windowed RISING-EDGE count of a boolean flag column — counted on the RAW rows (neuract.edge_count), so a register
    that flaps dozens of times inside one hour reports every real edge. (The old hourly-AVG bucket loop saw a flapping
    flag as permanently asserted → ~1 edge/day — the '0 events vs 25-32 real edges' defect family.) None when the column
    is absent / the table is empty (honest); a quiet present flag → a real 0."""
    w = window or (None, None)
    return _nx.edge_count(asset_table, col, w[0], w[1])


def _bucketed_values(field, asset_table, present_cols, quantity, window, element_skeleton=None):
    """A history/trend series leaf (kind='bucketed', or a raw field whose target leaf is an array).

    Reads ONE column down-sampled over the ctx window via neuract.bucketed(). Each point is _verify'd (denorm-garbage →
    None; negative power/energy → abs) so the series carries the SAME clean values a scalar leaf would. Honest-degrade →
    [] when the column is absent / the table is empty / the window has no rows — preserving the array container type so
    the frontend still .map()s over an empty list, NEVER a fabricated series.

    SHAPE-AWARE [frontend-contract array-of-objects family, card 42]: many CMD_V2 series props are arrays of OBJECTS
    (LoadAnomalyPoint {time, value}, {t, value}, …), NOT raw numbers — the component destructures p.time / p.value. When
    the target leaf's ELEMENTS are objects (`element_skeleton` is a dict), we emit objects that PRESERVE that element's
    shape (its value key filled with the reading, its time key with the bucket timestamp, every other chrome key kept),
    so `.forEach(p => p.time)` / yScale(p.value) never hit NaN. A raw-number series leaf (no object skeleton) stays a
    plain value array. Generic — the value/time key names come from the element skeleton, no hardcoded card shape."""
    col = field.get("column")
    if not (col and col in present_cols):
        return []                                              # no real column → empty array (honest-degrade)
    w = window or (None, None)
    sampling = field.get("sampling") or "hourly"
    series = _nx.bucketed(asset_table, col, w[0], w[1], sampling=sampling)  # [{t, value}] ascending, [] on degrade
    vals = [_verify(pt.get("value"), quantity=quantity) for pt in series]
    if isinstance(element_skeleton, dict):
        # ARRAY-OF-OBJECTS target: fill each element preserving its own shape (value key ← reading, time key ← bucket ts).
        vkey = _element_value_key(element_skeleton)
        tkey = _element_time_key(element_skeleton)
        out = []
        for pt, v in zip(series, vals):
            el = dict(element_skeleton)                         # keep the element's chrome keys byte-identical
            if vkey:
                el[vkey] = v
            if tkey:
                el[tkey] = _epoch_ms(pt.get("t"))
            out.append(el)
        return out
    # EXTRACT the ORDERED value array; _verify each point (order + None-for-missing-bucket preserved).
    return vals


def _element_value_key(skel):
    """The VALUE key of a series-element object skeleton ({time, value} → 'value'; {t, min, max} → None: a band has no
    single value key). REUSES the existing DB vocabulary config.vocab('element_value_keys') — the SAME enumeration
    leaf_classify uses for series-of-objects value slots — with a code default; None when the element carries no single
    numeric value slot (a band/multi-value element is left to the roster/element path)."""
    try:
        from config.vocab import vocab
        keys = [str(k) for k in (vocab("element_value_keys") or [])]
    except Exception:
        keys = []
    for k in (keys or ["value", "values", "y", "kw", "kwh", "count"]):
        if k in skel:
            return k
    return None


# A series-element's TIME key ({time,value}→'time'; {t,value}→'t'). The DB time_axis_keys vocab lists the PAGE-level
# axis leaf names (sampleTimestamps/…), not the per-ELEMENT time key, so this small closed set is the code default
# (extendable via the app_config vocab 'series_time_keys' row when a new data shape needs it).
def _element_time_key(skel):
    """The TIME key of a series-element object skeleton ({time, value} → 'time'; {t, value} → 't'). Optional DB override
    (config.vocab 'series_time_keys') else the closed code default; None when the element carries no time slot."""
    try:
        from config.vocab import vocab
        keys = [str(k) for k in (vocab("series_time_keys") or [])]
    except Exception:
        keys = []
    for k in (keys or ["time", "t", "ts", "timestamp"]):
        if k in skel:
            return k
    return None


def _epoch_ms(iso):
    """ISO timestamp string → epoch milliseconds int, or None (honest-degrade on unparseable)."""
    try:
        from datetime import datetime
        return int(datetime.fromisoformat(str(iso)).timestamp() * 1000)
    except Exception:
        return None


def _is_time_field(field, leaf_key):
    """A TIME-AXIS field: kind='time' (the prompt contract), OR — compat net for an AI that still binds a timestamp
    column — its column names the time axis ('ts'/'time'/'timestamp*'), OR its leaf key is in the DB-driven time-axis
    vocabulary (config.vocab time_axis_keys)."""
    if (field.get("kind") or "").lower() == "time":
        return True
    col = (field.get("column") or "").lower()
    if col in ("ts", "time", "timestamp", "timestamp_utc"):
        return True
    # compat: an AI that declares the time axis via `metric` (a null-column bucketed field, metric='ts'/'time') rather
    # than kind='time' — the composite [*].label point-time slot. The declared metric names the time axis, not a column.
    if (field.get("metric") or "").lower() in ("ts", "time", "timestamp", "timestamp_utc") and not field.get("column"):
        return True
    try:
        from config.vocab import vocab
        keys = {str(k).lower() for k in (vocab("time_axis_keys") or [])}
    except Exception:
        keys = set()                                           # vocab row unreachable → key-vocab signal off (honest)
    k = (leaf_key or "").lower()
    return k in keys or "timestamp" in k or k.endswith(("startms", "endms"))


def _anchor_timestamps(fields, asset_table, present_cols, window):
    """The card's bucket-timestamp axis (epoch ms, ascending) — from the FIRST series field with a REAL column (the
    anchor). Every time-axis leaf on the card fills from THIS one list so points and x-axis always align. [] when the
    card has no real-column series (honest-degrade: an axis without data is meaningless)."""
    for f in fields:
        kind = (f.get("kind") or "raw").lower()
        col = f.get("column")
        if kind in ("bucketed", "raw", "") and col and col in present_cols:
            # any real-column series/raw candidate anchors the axis
            w = window or (None, None)
            series = _nx.bucketed(asset_table, col, w[0], w[1], sampling=f.get("sampling") or "hourly")
            if series:
                return [_epoch_ms(pt.get("t")) for pt in series]
    return []
