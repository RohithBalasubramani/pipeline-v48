"""tests/test_canonical_slots.py — canonical voltage-monitor contract-slot completion (ems_exec/executor/canonical_slots).

Pins: flag-off byte-identity; unbound legend/metric slots backfill from the slot's own label; AI binds are NEVER
overridden; the statutory ±band injects only when both threshold value slots are unbound + a band is recoverable;
non-voltage cards (Current Monitor) are untouched; honest-degrade on a missing band."""
from unittest.mock import patch

from ems_exec.executor import canonical_slots as C


def _skeleton():
    """A Voltage Monitor Panel skeleton (subset) — legend/metrics/thresholds slots + a Voltage y-axis."""
    return {"data": {
        "yAxisLabel": "Voltage",
        "series": [{"color": "#1"}, {"color": "#2"}, {"color": "#3"}],
        "legendItems": [{"label": "B-Phase", "value": 0}, {"label": "R-Phase", "value": 0},
                        {"label": "Y-Phase", "value": 0}],
        "metrics": [{"label": "Average", "value": 0}, {"label": "Max", "value": 0}, {"label": "Min", "value": 0}],
        "thresholds": [{"label": "", "value": 0}, {"label": "", "value": 0}],
    }}


def _slots(di):
    return {f["slot"]: f for f in (di.get("fields") or [])}


def _band_ok(asset):
    return {"min": 5716.0, "max": 6986.0, "nominal": 6351.0}


# ── flag off = byte-identical ────────────────────────────────────────────────────────────────────────────────────────

def test_flag_off_is_noop():
    di = {"fields": [{"slot": "data.metrics[0].value", "kind": "raw", "column": "voltage_avg"}]}
    with patch.object(C, "_on", lambda: False):
        out = C.inject(_skeleton(), di, "gic_x")
    assert out is di                                                    # same object, untouched


# ── legend / metrics backfill (unbound only) ─────────────────────────────────────────────────────────────────────────

def test_backfills_unbound_legend_and_metrics_by_label():
    di = {"fields": []}
    with patch.object(C, "_on", lambda: True), patch.object(C, "_statutory_band", _band_ok):
        out = C.inject(_skeleton(), di, "gic_x")
    s = _slots(out)
    assert s["data.legendItems[0].value"]["column"] == "voltage_b_n"    # B-Phase
    assert s["data.legendItems[1].value"]["column"] == "voltage_r_n"    # R-Phase
    assert s["data.legendItems[2].value"]["column"] == "voltage_y_n"    # Y-Phase
    assert s["data.metrics[0].value"]["column"] == "voltage_avg"
    assert s["data.metrics[1].value"]["column"] == "voltage_max"
    assert s["data.metrics[2].value"]["column"] == "voltage_min"
    assert all(f.get("_canonical") for f in out["fields"])              # every injected field is flagged canonical


def test_never_overrides_an_ai_bind():
    # the AI bound legendItems[0] to a DIFFERENT column (a deliberate override) — canonical must leave it alone
    di = {"fields": [{"slot": "data.legendItems[0].value", "kind": "raw", "column": "voltage_ry"}]}
    with patch.object(C, "_on", lambda: True), patch.object(C, "_statutory_band", _band_ok):
        out = C.inject(_skeleton(), di, "gic_x")
    binds = [f for f in out["fields"] if f["slot"] == "data.legendItems[0].value"]
    assert len(binds) == 1 and binds[0]["column"] == "voltage_ry"       # untouched, not duplicated


# ── statutory band → shaded region ───────────────────────────────────────────────────────────────────────────────────

def test_band_injected_as_const_value_and_label():
    di = {"fields": []}
    with patch.object(C, "_on", lambda: True), patch.object(C, "_statutory_band", _band_ok):
        out = C.inject(_skeleton(), di, "gic_x")
    s = _slots(out)
    assert s["data.thresholds[0].value"]["value"] == 6986.0            # max = band top
    assert s["data.thresholds[1].value"]["value"] == 5716.0            # min = band bottom
    assert s["data.thresholds[0].label"]["value"] == "Max - 6986V"
    assert s["data.thresholds[1].label"]["value"] == "Min - 5716V"


def test_band_not_injected_when_ai_already_bound_thresholds():
    di = {"fields": [{"slot": "data.thresholds[0].value", "kind": "raw", "column": "voltage_avg"},
                     {"slot": "data.thresholds[1].value", "kind": "raw", "column": "voltage_avg"}]}
    with patch.object(C, "_on", lambda: True), patch.object(C, "_statutory_band", _band_ok):
        out = C.inject(_skeleton(), di, "gic_x")
    consts = [f for f in out["fields"] if f["slot"].startswith("data.thresholds") and f["kind"] == "const"]
    assert consts == []                                                # AI band preserved, no const overlay


def test_no_band_recovered_is_honest_blank():
    di = {"fields": []}
    with patch.object(C, "_on", lambda: True), patch.object(C, "_statutory_band", lambda a: None):
        out = C.inject(_skeleton(), di, "gic_x")
    assert not any(f["slot"].startswith("data.thresholds") for f in out["fields"])   # no fabricated band


# ── scope guard: non-voltage card untouched ──────────────────────────────────────────────────────────────────────────

def test_current_monitor_untouched():
    cur = {"data": {"yAxisLabel": "Current",
                    "legendItems": [{"label": "R-Phase", "value": 0}],
                    "thresholds": [{"label": "", "value": 0}, {"label": "", "value": 0}]}}
    di = {"fields": []}
    with patch.object(C, "_on", lambda: True), patch.object(C, "_statutory_band", _band_ok):
        out = C.inject(cur, di, "gic_x")
    assert out is di                                                    # not a voltage card → no-op


def test_voltage_card_detected_by_bound_column_when_axis_absent():
    sk = {"data": {"legendItems": [{"label": "B-Phase", "value": 0}], "thresholds": []}}
    di = {"fields": [{"slot": "data.series[0].data", "kind": "bucketed", "column": "voltage_r_n"}]}
    with patch.object(C, "_on", lambda: True), patch.object(C, "_statutory_band", _band_ok):
        out = C.inject(sk, di, "gic_x")
    assert _slots(out)["data.legendItems[0].value"]["column"] == "voltage_b_n"


# ── F7: aggregate-from-phases swap ───────────────────────────────────────────────────────────────────────────────────

def _patch_latest(row):
    import ems_exec.data.neuract as NX
    return patch.object(NX, "latest", lambda table, cols: {c: row.get(c) for c in cols})


def test_f7_flag_off_no_swap():
    di = {"fields": [{"slot": "data.metrics[2].value", "kind": "raw", "column": "current_avg"}]}
    with patch.object(C, "_on", lambda: False), patch.object(C, "_agg_on", lambda: False):
        out = C.inject({"data": {}}, di, "gic_x")
    assert out is di


def test_f7_swaps_dead_aggregate_to_phase_derivation():
    di = {"fields": [{"slot": "data.metrics[2].value", "kind": "raw", "column": "current_avg", "metric": "current_avg"}]}
    row = {"current_avg": None, "current_r": 45.0, "current_y": 46.0, "current_b": 44.0}
    with patch.object(C, "_on", lambda: False), patch.object(C, "_agg_on", lambda: True), _patch_latest(row):
        out = C.inject({"data": {"yAxisLabel": "Amps"}}, di, "gic_x")
    f = _slots(out)["data.metrics[2].value"]
    assert f["kind"] == "derived" and f["fn"] == "phaseCurrentAvg" and f["column"] is None
    assert f["_canonical"] == "agg_from_phases"


def test_f7_live_aggregate_is_left_alone():
    # current_avg has a real value on this meter → keep the meter's own register, do NOT swap
    di = {"fields": [{"slot": "data.metrics[2].value", "kind": "raw", "column": "current_avg"}]}
    row = {"current_avg": 45.3, "current_r": 45.0, "current_y": 46.0, "current_b": 44.0}
    with patch.object(C, "_on", lambda: False), patch.object(C, "_agg_on", lambda: True), _patch_latest(row):
        out = C.inject({"data": {}}, di, "gic_x")
    assert out is di                                              # nothing changed


def test_f7_components_absent_stays_honest_blank():
    di = {"fields": [{"slot": "data.metrics[2].value", "kind": "raw", "column": "current_avg"}]}
    row = {"current_avg": None, "current_r": None, "current_y": None, "current_b": None}
    with patch.object(C, "_on", lambda: False), patch.object(C, "_agg_on", lambda: True), _patch_latest(row):
        out = C.inject({"data": {}}, di, "gic_x")
    assert out is di                                              # no components → no swap, honest-blank preserved


def test_f7_derivations_compute_mean_and_unbalance():
    from ems_exec.derivations import current as CUR
    ctx = {"row": {"current_r": 45.0, "current_y": 46.0, "current_b": 44.0}}
    assert CUR.phase_current_avg(ctx) == 45.0
    assert CUR.phase_current_unbalance_pct(ctx) == round((46.0 - 44.0) / 45.0 * 100, 1)
    assert CUR.phase_current_avg({"row": {}}) is None


# ── F6: statutory-band geometry on sibling voltage cards ─────────────────────────────────────────────────────────────

def _history_skeleton():
    """The real Voltage History (card-44) shape — root key 'history' (NOT 'data'); maxLine/minLine bound to the meter's
    data extent, only expectedMax/expectedMin unbound; a structured maxLine.label object."""
    return {"history": {"data": {
        "yAxisLabel": "Voltage",
        "series": [{"data": [1, 2, 3]}],
        "maxLine": {"value": 0, "label": {"prefix": "Max: ", "value": "—", "unit": "V"}},
        "minLine": {"value": 0, "label": {"prefix": "Min: ", "value": "—", "unit": "V"}},
        "expectedMax": None, "expectedMin": None,
    }}}


def _history_di():
    # maxLine/minLine are the DATA extent (bound to voltage_max/min); expected* is the statutory band (unbound)
    return {"fields": [
        {"slot": "history.data.series[0].data", "kind": "bucketed", "column": "voltage_r_n"},
        {"slot": "history.data.maxLine.value", "kind": "raw", "column": "voltage_max"},
        {"slot": "history.data.minLine.value", "kind": "raw", "column": "voltage_min"},
    ]}


def test_f6_fills_expected_band_from_nameplate_band_root_history():
    with patch.object(C, "_band_geo_on", lambda: True), patch.object(C, "_statutory_band", _band_ok):
        out = C.inject(_history_skeleton(), _history_di(), "gic_x")
    s = _slots(out)
    assert s["history.data.expectedMax"]["value"] == 6986.0                # unbound → statutory band
    assert s["history.data.expectedMin"]["value"] == 5716.0
    # maxLine/minLine were AI-bound to the data extent → NOT overridden (still the raw voltage_max/min bind)
    assert s["history.data.maxLine.value"].get("column") == "voltage_max" and s["history.data.maxLine.value"].get("_canonical") is None
    assert not any(f["slot"] == "history.data.maxLine.label" for f in out["fields"])   # structured label left alone


def test_f6_dg_shape_unbound_lines_fill_with_scalar_label():
    # card-67 DG shape: root-level maxLine/minLine with a SCALAR label, all unbound → fill value + label from band
    sk = {"yAxisLabel": "Voltage", "series": [{"data": [1]}],
          "maxLine": {"value": 0, "label": ""}, "minLine": {"value": 0, "label": ""}}
    di = {"fields": [{"slot": "series[0].data", "kind": "bucketed", "column": "voltage_r_n"}]}
    with patch.object(C, "_band_geo_on", lambda: True), patch.object(C, "_statutory_band", _band_ok):
        out = C.inject(sk, di, "gic_x")
    s = _slots(out)
    assert s["maxLine.value"]["value"] == 6986.0 and s["minLine.value"]["value"] == 5716.0
    assert s["maxLine.label"]["value"] == "Max: 6986V"


def test_f6_flag_off_noop():
    with patch.object(C, "_band_geo_on", lambda: False), patch.object(C, "_on", lambda: False), \
         patch.object(C, "_agg_on", lambda: False):
        di = _history_di()
        out = C.inject(_history_skeleton(), di, "gic_x")
    assert out is di


def test_f6_no_band_recovered_is_honest_blank():
    with patch.object(C, "_band_geo_on", lambda: True), patch.object(C, "_statutory_band", lambda a: None):
        di = _history_di()
        out = C.inject(_history_skeleton(), di, "gic_x")
    assert out is di                                                       # no band → nothing filled
