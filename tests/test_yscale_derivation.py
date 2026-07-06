"""ems_exec executor — POST-FILL Y-SCALE DERIVATION (cards 44/46/48/49), pure unit tests (no DB, no LLM).

A chart's {maxY, minY, yTicks} scale object is stripped to 0.0 so a real filled series renders OFF-SCALE
(yRange=maxY-minY||1=1). The executor now recomputes the scale from the sibling series' OWN min/max after fill. These
assert: real series → derived padded bounds + regenerated ticks; empty series → honest-blank scale (never a fabricated
axis); expected-band leaves are DATA, left untouched (never a fabricated envelope); both maxY/minY and yMax/yMin
namings; nested view objects (DistortionProfileChart views) each derive their own scale."""
from __future__ import annotations

from ems_exec.executor import yscale as Y


def test_real_series_derives_padded_bounds_and_ticks():
    out = Y.apply({"history": {"data": {
        "maxY": 0.0, "minY": 0.0, "yTicks": [0, 0, 0, 0, 0],
        "series": [{"label": "R", "values": [418.0, 420.5, 235.0]}, {"label": "Y", "values": [419.1, 233.9]}]}}})
    d = out["history"]["data"]
    assert d["minY"] < 235.0 and d["maxY"] > 420.5               # bounds bracket the real range with headroom
    assert d["yTicks"][0] == d["maxY"] and d["yTicks"][-1] == d["minY"]  # ticks span the derived axis, descending
    assert all(a >= b for a, b in zip(d["yTicks"], d["yTicks"][1:]))    # strictly descending


def test_expected_band_leaves_are_data_left_untouched():
    out = Y.apply({"data": {"maxY": 0.0, "minY": 0.0, "yTicks": [0, 0],
                            "expectedMax": 0.0, "expectedMin": 0.0,
                            "series": [{"values": [270.0, 260.0]}]}})
    d = out["data"]
    assert d["maxY"] != 0.0                                       # axis derived
    assert d["expectedMax"] == 0.0 and d["expectedMin"] == 0.0    # data band NOT fabricated by the axis pass


def test_empty_series_leaves_honest_blank_scale():
    out = Y.apply({"v": {"maxY": 0.0, "minY": 0.0, "yTicks": [0, 0], "series": [{"values": []}]}})
    assert out["v"]["maxY"] == 0.0 and out["v"]["minY"] == 0.0    # no real data → no fabricated axis


def test_ymax_ymin_naming_variant():
    out = Y.apply({"v": {"yMax": 0.0, "yMin": 0.0, "yTicks": [0, 0, 0], "series": [{"values": [6.0, 10.0, 8.0]}]}})
    assert out["v"]["yMax"] > 10.0 and out["v"]["yMin"] < 6.0


def test_flat_series_gets_a_band_not_a_zero_range_axis():
    out = Y.apply({"v": {"yMax": 0.0, "yMin": 0.0, "yTicks": [0, 0, 0], "series": [{"values": [270.0, 270.0]}]}})
    assert out["v"]["yMax"] > out["v"]["yMin"]                    # never a zero-range axis on a flat line


def test_nested_view_objects_each_derive_their_own_scale():
    # DistortionProfileChart: distortionProfile.views.{v-thd,i-thd} each with its own {yMax,yMin,series}
    out = Y.apply({"distortionProfile": {"views": {
        "v-thd": {"yMax": 0.0, "yMin": 0.0, "yTicks": [0, 0], "series": [{"values": []}]},
        "i-thd": {"yMax": 0.0, "yMin": 0.0, "yTicks": [0, 0], "series": [{"values": [6.0, 10.0]}]}}}})
    v = out["distortionProfile"]["views"]
    assert v["v-thd"]["yMax"] == 0.0                              # empty view stays honest-blank
    assert v["i-thd"]["yMax"] > 10.0                             # data view derives its own axis
