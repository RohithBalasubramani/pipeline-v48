"""ems_exec executor — CHROME GUARD for the `chart.axes` config-object array (cards 61/62 family), pure unit tests
(no DB, no LLM). Some CMD_V2 chart primitives (thermal/mech dual-axis) keep `chart.axes` as a list of axis-CONFIG
OBJECTS ({id, domain, orientation, …}) — pure chrome defining the scale, NOT a time-values array. Layer 2 sometimes
emits a kind='time' field pointing at that slot; the old executor saw "a list" + "a time field" and overwrote the
config objects with epoch-ms timestamps, DESTROYING the axis config (the judge flagged 'chrome keys lost:
chart.axes[0]/[1]'). These assert the executor now PRESERVES a list-of-dicts (chrome) byte-for-byte, while a genuine
scalar-list time leaf still fills — GENERICALLY (no card ids; the discriminator is the element shape)."""
from __future__ import annotations

import ems_exec.data.neuract as nx
import config.nameplates as npr
from ems_exec.executor import fill as F


class _StubNeuract:
    """Patch neuract so fill() runs offline: 1 present real column with a 2-point ascending bucketed series."""

    def __enter__(self):
        self._b, self._p, self._l = nx.bucketed, nx.present_columns, nx.latest
        self._r = npr.derive_ratings_for
        nx.present_columns = lambda t: frozenset({"active_power_total_kw"})
        nx.latest = lambda t, cols: {"active_power_total_kw": 5.0}
        nx.bucketed = lambda t, c, s, e, sampling="hourly": [
            {"t": "2026-01-01T00:00:00", "value": 10.5},
            {"t": "2026-01-01T01:00:00", "value": 11.2},
        ]
        npr.derive_ratings_for = lambda t: {}
        return self

    def __exit__(self, *a):
        nx.bucketed, nx.present_columns, nx.latest = self._b, self._p, self._l
        npr.derive_ratings_for = self._r


_CONFIG_AXES = [
    {"id": "temp", "domain": [20, 130], "orientation": "left"},
    {"id": "exh", "domain": [0, 680], "orientation": "right"},
]


def _fill(payload, fields, default_payload=None):
    with _StubNeuract():
        return F.fill(payload, {"fields": fields}, {"asset_table": "tbl", "window": (None, None)},
                      default_payload=default_payload)


_SERIES_CFG = [  # a config-object series: line DEFINITIONS (key/axis/name), NO data-point value/time key — pure chrome
    {"key": "coolant", "axis": "temp", "name": "Coolant", "trip": 104, "warn": 95, "color": "#7ab8d2"},
    {"key": "exhaust", "axis": "exh", "name": "Exhaust", "trip": 620, "warn": 560, "color": "#d27a7a"},
]


def test_axis_config_object_array_is_preserved_not_overwritten_with_timestamps():
    # chart.axes = a list of 2 axis-CONFIG objects (chrome). A kind='time' field points at it (as Layer 2 emitted for
    # cards 61/62). The guard must leave the config objects intact — NO timestamps, structure byte-identical.
    payload = {"chart": {"axes": [dict(a) for a in _CONFIG_AXES], "series": []}}
    out = _fill(payload, [{"slot": "chart.axes", "kind": "time"}])
    assert out["chart"]["axes"] == _CONFIG_AXES                  # chrome preserved exactly (no clobber)
    assert all(isinstance(a, dict) for a in out["chart"]["axes"])


def test_config_object_series_elided_to_none_is_restored_from_default_not_flattened():
    # THE LIVE PATH: the byte-identity gate elides chart.series (a config-object array) to None; a bucketed field then
    # tries to fill it. Without the default-shape guard the executor flattened it to a raw number array (chart geometry
    # lost). The guard must RESTORE the config-object array byte-identical from the default + record the gap. [cards 61/62]
    default = {"chart": {"series": [dict(s) for s in _SERIES_CFG]}}
    payload = {"chart": {"series": None}}                        # gate elided the config array to None
    out = _fill(payload, [{"slot": "chart.series", "kind": "bucketed", "column": "active_power_total_kw"}],
                default_payload=default)
    se = out["chart"]["series"]
    assert isinstance(se, list) and len(se) == len(_SERIES_CFG)  # restored as the config-object array, not flattened
    assert all(isinstance(s, dict) for s in se)
    assert se[0]["key"] == "coolant" and se[0]["trip"] == 104    # real chrome (thresholds/colors) preserved byte-identical
    assert not any(isinstance(x, (int, float)) and not isinstance(x, bool) for x in se)  # never a flat number array


def test_config_object_series_present_is_also_preserved():
    # same guard when the config array is PRESENT (not None-elided): a bucketed field must not flatten it.
    default = {"chart": {"series": [dict(s) for s in _SERIES_CFG]}}
    payload = {"chart": {"series": [dict(s) for s in _SERIES_CFG]}}
    out = _fill(payload, [{"slot": "chart.series", "kind": "bucketed", "column": "active_power_total_kw"}],
                default_payload=default)
    assert out["chart"]["series"] == _SERIES_CFG                 # config chrome intact


def test_scalar_time_axis_list_still_fills_with_bucket_timestamps():
    # a genuine time-VALUES leaf (list of scalars) still fills from the bucket axis — the guard only spares dict-lists.
    payload = {"chart": {"sampleTimestamps": [0, 0], "series": []},
               "data": {"active_power_total_kw": [0.0, 0.0]}}
    out = _fill(payload, [{"slot": "chart.sampleTimestamps", "kind": "time"},
                          {"slot": "data.active_power_total_kw", "kind": "bucketed",
                           "column": "active_power_total_kw"}])
    ts = out["chart"]["sampleTimestamps"]
    assert isinstance(ts, list) and ts and all(isinstance(x, int) for x in ts)   # filled with epoch-ms scalars
