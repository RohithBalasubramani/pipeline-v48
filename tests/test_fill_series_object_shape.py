"""ems_exec executor — SHAPE-AWARE series fill (card-42 frontend-contract family), pure unit tests (no DB, no LLM).

Many CMD_V2 series props are arrays of OBJECTS (LoadAnomalyPoint {time, value}, {t, value}, …) — the component
destructures p.time / p.value / yScale(p.value). The old executor filled EVERY bucketed series leaf with RAW NUMBERS,
so an object-array slot became [num, num, …] and `.forEach(p => p.time)` hit NaN geometry (the card-42 all-broken
chart). These assert the executor now fills OBJECTS when the target element is an object, and stays a plain value array
otherwise — GENERICALLY (value/time key names come from the element skeleton, no hardcoded card shape)."""
from __future__ import annotations

import ems_exec.data.neuract as nx
from ems_exec.executor import fill as F


class _StubBucketed:
    """Patch neuract.bucketed to a fixed 2-point ascending series for the duration of a test."""

    def __enter__(self):
        self._orig = nx.bucketed
        nx.bucketed = lambda t, c, s, e, sampling="hourly": [
            {"t": "2026-01-01T00:00:00", "value": 10.5},
            {"t": "2026-01-01T01:00:00", "value": 11.2},
        ]
        return self

    def __exit__(self, *a):
        nx.bucketed = self._orig


def test_raw_number_series_stays_a_value_array():
    with _StubBucketed():
        out = F._bucketed_values({"column": "active_power_total_kw"}, "tbl",
                                 {"active_power_total_kw"}, "power", (None, None))
    assert out == [10.5, 11.2]


def test_object_series_fills_objects_matching_element_shape():
    with _StubBucketed():
        out = F._bucketed_values({"column": "active_power_total_kw"}, "tbl",
                                 {"active_power_total_kw"}, "power", (None, None),
                                 element_skeleton={"time": 0, "value": 0.0})
    assert all(isinstance(p, dict) for p in out)                 # OBJECTS, never raw numbers
    assert {"time", "value"} <= set(out[0].keys())
    assert out[0]["value"] == 10.5 and out[1]["value"] == 11.2   # value filled from the reading
    assert all(isinstance(p["time"], int) for p in out)          # time filled with the bucket epoch-ms


def test_alt_key_names_t_and_v_are_honored_from_skeleton():
    # a {t, value} element (the {t,value} history-series shape) fills its own key names, not a hardcoded 'time'
    with _StubBucketed():
        out = F._bucketed_values({"column": "x"}, "tbl", {"x"}, "power", (None, None),
                                 element_skeleton={"t": 0, "value": 0.0})
    assert "t" in out[0] and out[0]["value"] == 10.5


def test_band_element_without_single_value_key_is_left_for_the_element_path():
    # an expectedRange band {min, max, time} has NO single value key → _element_value_key None → objects still emitted
    # but the value slot is untouched (the band's min/max are filled by the roster/element path, not this scalar fill).
    with _StubBucketed():
        vkey = F._element_value_key({"min": 0.0, "max": 0.0, "time": 0})
    assert vkey is None


def test_absent_column_honest_degrades_to_empty_array():
    out = F._bucketed_values({"column": "nope"}, "tbl", {"present_col"}, "power", (None, None),
                             element_skeleton={"time": 0, "value": 0.0})
    assert out == []                                             # honest-blank, never a fabricated object series
