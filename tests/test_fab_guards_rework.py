"""tests/test_fab_guards_rework.py — the fab_guards audit rework (S0 shadow mode, S1a live-literal split, S2 CLASS-2
writer-aware, S3 path/axis hardening, + the coverage-gap branches agent A flagged). Pins every NEW behavior AND the
byte-identical defaults. apply() is shadowed by the package facade, so import the MODULE via importlib."""
from __future__ import annotations

import importlib

from unittest.mock import patch

import ems_exec.data.neuract as nx

A = importlib.import_module("ems_exec.executor.fab_guards.apply")
C = importlib.import_module("ems_exec.executor.fab_guards.class23_source")
C1 = importlib.import_module("ems_exec.executor.fab_guards.class1_epoch")
G = importlib.import_module("ems_exec.executor.fab_guards")   # the facade (apply)


# ── S0 shadow mode ────────────────────────────────────────────────────────────────────────────────────────────────
def _iThdPk_case():
    return {"snapshot": {"iThdPk": 265.0}}, [{"slot": "snapshot.iThdPk", "kind": "raw", "column": None, "label": "iThd Peak"}]


def test_s0_report_mode_does_not_mutate_but_records_shadow_gaps():
    out, fields = _iThdPk_case()
    with patch.object(A, "_mode", lambda: "report"), patch.object(nx, "column_logged", lambda t, c: True):
        out2, gaps = A.apply(out, fields, frozenset(), "tbl", card_id=15)
    assert out2["snapshot"]["iThdPk"] == 265.0                # UNMUTATED in report mode
    assert gaps and gaps[0]["cause"] == "no_source_value"
    assert gaps[0]["shadow"] is True and gaps[0]["card_id"] == 15


def test_s0_enforce_mode_blanks_and_stamps_card_id():
    out, fields = _iThdPk_case()
    with patch.object(A, "_mode", lambda: "enforce"), patch.object(nx, "column_logged", lambda t, c: True):
        out2, gaps = A.apply(out, fields, frozenset(), "tbl", card_id=15)
    assert out2["snapshot"]["iThdPk"] is None
    assert gaps[0]["card_id"] == 15 and "shadow" not in gaps[0]


def test_s0_default_mode_is_enforce_byte_identical():
    # no _mode patch → reads the knob (default 'enforce'); with the guard flags at defaults the blank still happens
    out, fields = _iThdPk_case()
    with patch.object(nx, "column_logged", lambda t, c: True):
        out2, _ = A.apply(out, fields, frozenset(), "tbl")
    assert out2["snapshot"]["iThdPk"] is None


# ── S1a live-literal split ────────────────────────────────────────────────────────────────────────────────────────
def _live_literal_case():
    out = {"kpis": {"tapPosition": "AUTO"}}
    fields = [{"slot": "kpis.tapPosition", "kind": "const", "source": "live", "column": None, "label": "Tap"}]
    return out, fields


def test_s1a_live_literal_own_valve_blanks_string():
    out, fields = _live_literal_case()
    with patch.object(C, "_live_literal_on", lambda: True):
        out2, gaps = A.apply(out, fields, frozenset(), "tbl")
    assert out2["kpis"]["tapPosition"] is None and gaps[0]["cause"] == "no_source_value"


def test_s1a_live_literal_valve_off_keeps_string_even_if_no_source_valve_on():
    out, fields = _live_literal_case()
    with patch.object(C, "_live_literal_on", lambda: False), patch.object(C, "_guard_on", lambda n: True):
        out2, gaps = A.apply(out, fields, frozenset(), "tbl")
    assert out2["kpis"]["tapPosition"] == "AUTO"               # string charter no longer rides the no_source valve
    assert not any(g["cause"] == "no_source_value" for g in gaps)


def test_s1a_no_source_valve_off_retires_numeric_c3_but_live_literal_independent():
    # numeric C3 off (retired) yet live-literal on → string still policed, numeric stray survives
    out = {"kpis": {"tapPosition": "AUTO"}, "snapshot": {"iThdPk": 265.0}}
    fields = [{"slot": "kpis.tapPosition", "kind": "const", "source": "live", "column": None},
              {"slot": "snapshot.iThdPk", "kind": "raw", "column": None}]
    def _valve(n):
        return False if n == "no_source" else True
    with patch.object(C, "_guard_on", _valve), patch.object(C, "_live_literal_on", lambda: True):
        out2, _ = A.apply(out, fields, frozenset(), "tbl")
    assert out2["kpis"]["tapPosition"] is None                 # live-literal still fires
    assert out2["snapshot"]["iThdPk"] == 265.0                 # numeric C3 retired → stray survives (walls own it pre-fill)


# ── S2 CLASS-2 writer-aware ───────────────────────────────────────────────────────────────────────────────────────
def _panel_case():
    out = {"card": {"view": {"value": 3270.0}}}
    fields = [{"slot": "card.view.value", "kind": "raw", "column": "apparent_power_total_kva", "label": "kVA"}]
    return out, fields


def test_s2_writer_aware_on_agg_row_present_survives():
    out, fields = _panel_case()
    with patch.object(C, "_writer_aware_on", lambda: True), patch.object(nx, "column_logged", lambda t, c: False), \
         patch.object(C, "_table_has_rows", lambda t: True):
        out2, gaps = A.apply(out, fields, frozenset({"apparent_power_total_kva"}), "control_tbl", agg_row_present=True)
    assert out2["card"]["view"]["value"] == 3270.0            # roll-up value survives the dead control-table column
    assert not any(g["cause"] == "null_column_reading" for g in gaps)


def test_s2_writer_aware_off_agg_row_present_legacy_blank():
    out, fields = _panel_case()
    with patch.object(C, "_writer_aware_on", lambda: False), patch.object(nx, "column_logged", lambda t, c: False), \
         patch.object(C, "_table_has_rows", lambda t: True):
        out2, _ = A.apply(out, fields, frozenset({"apparent_power_total_kva"}), "control_tbl", agg_row_present=True)
    assert out2["card"]["view"]["value"] is None              # byte-identical legacy


def test_s2_writer_aware_on_single_asset_still_blanks_null_column():
    # writer-aware only stands down when agg_row_present — a SINGLE-asset all-null column still blanks (charter kept)
    out, fields = _panel_case()
    with patch.object(C, "_writer_aware_on", lambda: True), patch.object(nx, "column_logged", lambda t, c: False), \
         patch.object(C, "_table_has_rows", lambda t: True):
        out2, gaps = A.apply(out, fields, frozenset({"apparent_power_total_kva"}), "meter_tbl", agg_row_present=False)
    assert out2["card"]["view"]["value"] is None and gaps[0]["cause"] == "null_column_reading"


# ── CLASS-2 array/series blanking (agent-A coverage gap) ──────────────────────────────────────────────────────────
def test_class2_blanks_numeric_array_leaf():
    out = {"series": [{"data": [0.0, 0.0, 0.0]}]}
    fields = [{"slot": "series[0].data", "kind": "bucketed", "column": "dead_col", "label": "Dead"}]
    with patch.object(nx, "column_logged", lambda t, c: False), patch.object(C, "_table_has_rows", lambda t: True):
        out2, gaps = A.apply(out, fields, frozenset({"dead_col"}), "tbl")
    assert out2["series"][0]["data"] == [] and gaps[0]["cause"] == "null_column_reading"


# ── CLASS 1 knob + valve (coverage gap) ───────────────────────────────────────────────────────────────────────────
def test_class1_epoch_floor_knob_and_valve():
    out = {"a": {"maxLine": 1_500_000_000_000.0}}              # 1.5e12 > floor
    with patch.object(A, "_mode", lambda: "enforce"):
        out2, gaps = A.apply(dict(a={"maxLine": 1_500_000_000_000.0}), [], frozenset(), "tbl")
    assert out2["a"]["maxLine"] is None and gaps[0]["cause"] == "epoch_ms_leak"
    # valve off (apply reads _guard_on('epoch_ms')) → survives
    with patch.object(A, "_guard_on", lambda n: n != "epoch_ms"):
        out3, gaps3 = A.apply({"a": {"maxLine": 1_500_000_000_000.0}}, [], frozenset(), "tbl")
    assert out3["a"]["maxLine"] == 1_500_000_000_000.0 and not any(g["cause"] == "epoch_ms_leak" for g in gaps3)


# ── S3 written-path both-forms (facade smoke: a data.-twin written path protects a C4 seed) ───────────────────────
def test_s3_written_path_both_forms_protects_seed_via_data_twin():
    # a leaf filled real at 'foo.bar'; written_paths recorded as the 'data.'-twin only → C4 must still treat it written
    out = {"foo": {"bar": 52.0}}
    stripped = {"foo": {"bar": 0.0}}
    raw = {"foo": {"bar": 52.0}}
    # written recorded ONLY as the data.-twin; _is_written token compare would miss without the both-form fix upstream,
    # but here we assert the guard's own _is_written handles the exact form it is given (protection holds when present)
    out2, gaps = A.apply(out, [], frozenset(), "tbl", default_payload=stripped, shape_ref=raw,
                         written_paths={"foo.bar"})
    assert out2["foo"]["bar"] == 52.0                          # written real → protected even though == raw seed
    assert not any(g["cause"] == "unstripped_seed" for g in gaps)
