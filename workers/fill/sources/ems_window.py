"""workers/fill/sources/ems_window.py — build the ems_backend WS query string (+ optional mid-connection date message)
from a consumer spec (layer2.emit.data.consumer_binding.build) and an optional RUNTIME date_window override (the user's
date pick on the frontend). LIVE endpoints → ?window=&interval=; HISTORY endpoints → ?range=|start=/end=&sampling=.
This is the DATE-NAVIGATION seam: the AI sets the DEFAULT window in the consumer; the frontend overrides it here. [#date-nav]"""
import json
from urllib.parse import quote, urlencode


def _derived_param(derived_map):
    """`&derived=<urlencoded JSON {target_column: fn}>` — the AI's row-scope recovery recipes for THIS endpoint, merged
    across all its cards. The ems_backend BaseLiveStrategy parses it into self.derived and its fill_derived(row) hook runs
    registry.run(fn, {"row": row}) to fill each target_column the DB returned as None. Empty/None → append nothing."""
    if not derived_map:
        return ""
    return f"&derived={quote(json.dumps(derived_map, separators=(',', ':')))}"


def query(consumer, date_window=None, derived_map=None):
    """Query string for ws/mfm/<id>/<endpoint>/?…  The frontend date_window overrides the AI's default range/sampling.
    `derived_map` ({target_column: fn}) appends the row-scope recovery recipes the ems_backend executor fills with."""
    c = consumer or {}
    dw = date_window or {}
    if c.get("is_history"):                                       # date-capable consumer
        rng = dw.get("range") or c.get("range")                   # the AI's range (or the user's pick); no hardcoded default
        sampling = dw.get("sampling") or c.get("sampling")        # the AI's sampling; omit → the consumer's own default applies
        params = {}
        if rng:
            params["range"] = rng
        if sampling:
            params["sampling"] = sampling
        start = dw.get("start") or c.get("start")
        end = dw.get("end") or c.get("end")
        if rng == "custom-range" and start and end:
            params["start"], params["end"] = start, end
        return urlencode({k: v for k, v in params.items() if v}) + _derived_param(derived_map)
    params = {}                                                  # live trailing-window consumer
    if c.get("window_seconds"):
        params["window"] = int(c["window_seconds"])
    if c.get("interval_seconds"):
        params["interval"] = c["interval_seconds"]
    return urlencode(params) + _derived_param(derived_map)


def date_message(consumer, date_window=None):
    """The mid-connection JSON that re-windows a HISTORY consumer without reconnecting (or None for live / no override)."""
    c, dw = consumer or {}, date_window or {}
    if not c.get("is_history") or not dw:
        return None
    msg = {k: dw[k] for k in ("range", "sampling", "start", "end") if dw.get(k)}
    return msg or None
