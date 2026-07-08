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


# ── CONSTANT / ALL-ZERO GUARANTEE [DG-1 card 36 family, 2026-07-07] ──────────────────────────────────────────────
# An honest all-zero (or otherwise constant) filled series must ALWAYS ship explicit, sane y-scale leaves — the FE,
# given a constant series and no scale, degenerates its y-domain (epoch digits rendered as the y-axis).

def test_all_zero_series_ships_explicit_zero_to_one_axis():
    out = Y.apply({"v": {"yMax": 0.0, "yMin": 0.0, "yTicks": [0, 0, 0],
                         "series": [{"values": [0.0, 0.0, 0.0]}]}})
    assert out["v"]["yMin"] == 0.0 and out["v"]["yMax"] == 1.0    # explicit 0..1, honest zero floor
    assert out["v"]["yTicks"][0] == 1.0 and out["v"]["yTicks"][-1] == 0.0
    assert all(abs(t) < 1e6 for t in out["v"]["yTicks"])          # never an epoch-magnitude tick


def test_nonzero_constant_keeps_its_band_around_the_value():
    out = Y.apply({"v": {"yMax": 0.0, "yMin": 0.0, "series": [{"values": [270.0, 270.0]}]}})
    assert out["v"]["yMin"] < 270.0 < out["v"]["yMax"]            # band around the constant, line mid-axis


def _norm_shape():
    # card-36 shape oracle: normalized [0,1] dataSeries default + 6 numeric-string yLabels
    return {"data": {"dataSeries": [[0.2, 0.5, 0.8], [0.1, 0.3, 0.4]],
                     "yLabels": ["380", "340", "300", "120", "100", "80"]}}


def test_norm_series_all_zero_constant_ships_ylabels_and_keeps_zero_floor():
    # THE DG-1 card-36 defect: all-zero fill is inside [0,1] → looked "already normalized", yLabels stayed [].
    from ems_exec.executor import norm_series
    out = {"data": {"dataSeries": [[0.0] * 25, [0.0] * 25], "yLabels": []}}
    norm_series.apply(out, _norm_shape())
    labels = out["data"]["yLabels"]
    assert len(labels) == 6 and all(isinstance(x, str) for x in labels)   # explicit axis SHIPPED
    assert len(set(labels)) == 6                                          # duplicate-safe (never '1','1','0','0')
    fl = [float(x) for x in labels]
    assert fl[0] == 1.0 and fl[-1] == 0.0                                 # the explicit 0..1 all-zero domain
    assert all(a > b for a, b in zip(fl, fl[1:]))                         # max→min, strictly descending
    assert all(abs(x) < 1e6 for x in fl)                                  # no epoch-magnitude label
    assert all(x == 0.0 for s in out["data"]["dataSeries"] for x in s)    # honest zeros stay on the 0 floor


def test_norm_series_nonzero_constant_ships_band_labels_and_mid_axis_series():
    from ems_exec.executor import norm_series
    out = {"data": {"dataSeries": [[0.75, 0.75, 0.75]], "yLabels": []}}
    norm_series.apply(out, {"data": {"dataSeries": [[0.2, 0.5]], "yLabels": ["380", "340", "300", "80"]}})
    fl = [float(x) for x in out["data"]["yLabels"]]
    assert len(fl) == 4 and fl[0] > 0.75 > fl[-1]                         # band encloses the constant
    assert all(x == 0.5 for x in out["data"]["dataSeries"][0])            # constant re-anchored mid-axis


def test_norm_series_varying_series_keeps_current_scale_behavior():
    # a VARYING already-normalized fill is byte-untouched (no behavior change outside the constant case)
    from ems_exec.executor import norm_series
    out = {"data": {"dataSeries": [[0.2, 0.9, 0.4]], "yLabels": []}}
    norm_series.apply(out, _norm_shape())
    assert out["data"]["dataSeries"] == [[0.2, 0.9, 0.4]]
    assert out["data"]["yLabels"] == []


def test_norm_series_constant_never_clobbers_a_filled_label_axis():
    # a legit STRING-filled label axis stands; the constant series is then left exactly as filled
    from ems_exec.executor import norm_series
    out = {"data": {"dataSeries": [[0.0, 0.0, 0.0]], "yLabels": ["10", "5", "0"]}}
    norm_series.apply(out, {"data": {"dataSeries": [[0.2, 0.5]], "yLabels": ["380", "340", "80"]}})
    assert out["data"]["yLabels"] == ["10", "5", "0"]
    assert out["data"]["dataSeries"] == [[0.0, 0.0, 0.0]]


# ── GENERIC: the constant guarantee is keyed off the SERIES being constant, on ANY asset/metric/card ────────────────
# Prove the fix is class-level (shape-driven), not a DG-1 / one-card special-case: a flat metric on a UPS, a panel, a
# transformer — every magnitude — gets a sane band. Nothing here references a card id / slot name / prompt.

def _epoch_free(scale_vals):
    # the degenerate-domain class: NO served y-scale value may land in the epoch-magnitude band [1e9, 1e11).
    return all(not (1e9 <= abs(v) < 1e11) for v in scale_vals)


def test_constant_series_gets_sane_band_across_metrics_and_magnitudes():
    # off UPS (0), a flat 230 V bus, a full 0.85 SoC, a 20000 kVA nameplate-pinned flat, a flat -12.5 reactive kVAr —
    # each is a DIFFERENT asset/metric/card; all get an explicit non-degenerate band with NO epoch-magnitude value.
    for const, want_zero_floor in [(0.0, True), (230.0, False), (0.85, False),
                                   (20000.0, False), (-12.5, False)]:
        out = Y.apply({"c": {"yMax": 0.0, "yMin": 0.0, "yTicks": [0, 0, 0, 0, 0],
                             "series": [{"values": [const, const, const]}]}})
        d = out["c"]
        assert d["yMax"] > d["yMin"]                              # never a zero-range axis, whatever the magnitude
        if want_zero_floor:
            assert d["yMin"] == 0.0 and d["yMax"] == 1.0          # all-zero → honest 0..1 floor
        else:
            assert d["yMin"] < const < d["yMax"]                 # line sits mid-axis
        assert len(d["yTicks"]) == 5 and d["yTicks"][0] == d["yMax"] and d["yTicks"][-1] == d["yMin"]
        assert _epoch_free([d["yMax"], d["yMin"], *d["yTicks"]])  # (c) no [1e9,1e11) value survives


def test_varying_series_keeps_its_computed_scale_no_regression():
    # the constant guarantee must NOT touch a VARYING series: it keeps the padded data-driven bounds.
    out = Y.apply({"c": {"yMax": 0.0, "yMin": 0.0, "yTicks": [0, 0, 0],
                         "series": [{"values": [218.0, 233.0, 241.0, 226.0]}]}})
    d = out["c"]
    assert d["yMin"] < 218.0 and d["yMax"] > 241.0               # padded data range, not a constant band
    assert abs(d["yMin"] - (218.0 - (241.0 - 218.0) * 0.05)) < 1e-6   # exactly the 5% headroom convention
    assert _epoch_free([d["yMax"], d["yMin"], *d["yTicks"]])


def test_epoch_time_axis_sibling_never_drives_the_yscale():
    # a constant y-series beside an EPOCH-MS x-axis (both a *ms-suffixed list AND a bare >1e10 list) must derive its
    # scale from the CONSTANT series (0..1), never from the epoch axis — the exact source of the 3.4e9 degenerate axis.
    out = Y.apply({"c": {"yMax": 0.0, "yMin": 0.0, "yTicks": [0, 0, 0],
                         "timestampsMs": [1.77e12, 1.77e12 + 6e5, 1.77e12 + 12e5],
                         "epochAxis": [1.77e12, 1.77e12 + 6e5, 1.77e12 + 12e5],
                         "series": [{"values": [0.0, 0.0, 0.0]}]}})
    d = out["c"]
    assert d["yMin"] == 0.0 and d["yMax"] == 1.0                 # scale from the constant series, not the epoch lists
    assert _epoch_free([d["yMax"], d["yMin"], *d["yTicks"]])
    assert d["timestampsMs"][0] > 1e12 and d["epochAxis"][0] > 1e12   # the epoch axes themselves are untouched


def test_norm_series_constant_ylabels_are_never_epoch_magnitude():
    # the norm-strip label axis for an all-zero (and a non-zero) constant is a small 0..1 / banded domain — no epoch.
    from ems_exec.executor import norm_series
    for series, shape_labels in [([[0.0] * 20], ["380", "340", "300", "80"]),
                                 ([[0.9] * 20], ["380", "340", "300", "80"])]:
        out = {"data": {"dataSeries": series, "yLabels": []}}
        norm_series.apply(out, {"data": {"dataSeries": [[0.2, 0.5]], "yLabels": shape_labels}})
        fl = [float(x) for x in out["data"]["yLabels"]]
        assert len(fl) == 4 and _epoch_free(fl)


# ── DB-DRIVEN: every domain band is an app_config knob with a code-default MIRROR (byte-identical until a row edits) ─
# The accessors resolve the DB row; the module constants are the code default. Asserting they agree proves the mirror.

def test_band_knob_accessors_mirror_their_code_defaults():
    assert Y.const_zero_hi() == Y._DEFAULT_CONST_ZERO_HI == 1.0
    assert Y.const_band_halfwidth() == Y._DEFAULT_CONST_BAND_HALFWIDTH == 1.0
    assert Y.pad_pct() == Y._DEFAULT_PAD_PCT == 0.05
    from ems_exec.executor import norm_series as N
    assert N._DEFAULT_RANGE_PAD_PCT == 0.1 and N._DEFAULT_FLAT_PAD_MIN == 1.0 and N._DEFAULT_FLAT_PAD_PCT == 0.05


def test_band_knobs_are_db_driven_edit_changes_the_axis(monkeypatch):
    # a stubbed DB value flows through the accessor into the derived band — proving the literal is not baked in code.
    import ems_exec.executor.yscale as Ymod
    monkeypatch.setattr(Ymod, "_cfg_num",
                        lambda key, default, positive=False: 25.0 if key == "chart.const_axis_band_halfwidth"
                        else (0.20 if key == "chart.yscale_pad_pct" else default))
    assert Ymod._nice_bounds(270.0, 270.0) == (245.0, 295.0)     # ±25 band from the (stubbed) DB row
    lo, hi = Ymod._nice_bounds(0.0, 100.0)
    assert lo == -20.0 and hi == 120.0                           # 20% headroom from the (stubbed) DB row
