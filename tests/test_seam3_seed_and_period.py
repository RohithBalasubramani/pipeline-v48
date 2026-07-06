"""tests/test_seam3_seed_and_period.py — SEAM 3 (two seam fixes), PURE unit tests (no DB, no LLM, not live).

(A) SEED — layer2/build.py's `_default_payload` must be the SEEDLESS skeleton (card_payloads.payload_stripped, or a
    runtime blank of the raw copy), so no Storybook seed rides the L2 output to the executor's config-chrome byte-copy /
    container graft / offline replay. The c42 'Welding Overlap' seed (RAW payload) must NOT survive into a grafted
    container; the chrome STRUCTURE (dict keys) must stay byte-identical (only seed VALUES blanked).

(B) PERIOD — ems_exec/executor/fill.py must populate ctx[today|this_week|this_month] = {active_import, active_export,
    reactive_import, reactive_export} (each a real (end−start) counter delta) from the run window, so the reversed-CT
    windowed-energy fns compute their real delta (cards 36/43/44 previously false-blanked the reactive/apparent legs,
    which have no ∫power fallback). A GENUINELY-absent counter column still blanks (honest degradation, never fabricated).
"""
from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone

import ems_exec.data.neuract as nx
from ems_exec.executor import fill as F
from ems_exec.derivations import energy as E
from layer2.build import _seedfree_default


IST = timezone(timedelta(hours=5, minutes=30))


# ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────
#  (A) SEED — the c42-shaped default carries a Storybook 'Welding Overlap' seed that must NOT survive the graft source
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────
# A minimal c42 ('Load Anomalies') shape: data.anomalies[*] carries the seed prose/label; data.insight is seed prose;
# the CHROME (keys, colors, labels-that-are-config) must survive; the DATA-VALUE leaves get blanked.
_C42_RAW = {
    "data": {
        "insight": "Three load surges today — the largest a +25% welding overlap at 03:00.",
        "anomalies": [
            {"title": "Welding Overlap", "label": "Welding\nOverlap (+25%)",
             "detail": "Welding bay overlapped the press line — demand surged +25%.",
             "time": 3, "value": 25.0},
        ],
        "series": [{"color": "#f27e80", "label": "R phase", "values": [11.1, 11.2, 11.0]}],
        "yTicks": [11.8, 11.6, 11.4],
    }
}
# The STORED seedless skeleton for the same card — same chrome structure, seed VALUES blanked (what the builder persists
# into card_payloads.payload_stripped). This is what `_seedfree_default` returns when the stored column is present.
_C42_STRIPPED = {
    "data": {
        "insight": "",
        "anomalies": [{"title": "", "label": "", "detail": "", "time": 0, "value": 0.0}],
        "series": [{"color": "#f27e80", "label": "R phase", "values": []}],
        "yTicks": [],
    }
}


def _find(obj, needle, path=""):
    hits = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            hits += _find(v, needle, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            hits += _find(v, needle, f"{path}[{i}]")
    elif isinstance(obj, str) and needle.lower() in obj.lower():
        hits.append(path)
    return hits


def _dict_keys(obj, path=""):
    """Every dict-KEY path (the chrome structure), list indices collapsed to [*] (union across elements)."""
    out = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            kp = f"{path}.{k}"
            out.add(kp)
            out |= _dict_keys(v, kp)
    elif isinstance(obj, list):
        for v in obj:
            out |= _dict_keys(v, f"{path}[*]")
    return out


def test_seedfree_default_prefers_stored_stripped_and_drops_seed():
    dp = {"payload": copy.deepcopy(_C42_RAW), "payload_stripped": copy.deepcopy(_C42_STRIPPED)}
    sf = _seedfree_default(dp)
    assert _find(_C42_RAW, "Welding"), "fixture sanity: the RAW default must carry the seed"
    assert _find(sf, "Welding") == [], "the c42 'Welding Overlap' seed must NOT survive the seedless default"
    # the stored skeleton is used verbatim (identity), NOT the raw copy
    assert sf == _C42_STRIPPED


def test_seedfree_default_preserves_chrome_structure_byte_for_byte():
    dp = {"payload": copy.deepcopy(_C42_RAW), "payload_stripped": copy.deepcopy(_C42_STRIPPED)}
    sf = _seedfree_default(dp)
    # zero chrome (dict-key) paths dropped — only VALUES were blanked, the shape the FE mapper keys on is intact
    assert _dict_keys(_C42_RAW) - _dict_keys(sf) == set()


def test_seedfree_default_fallback_blanks_raw_when_stored_absent():
    # no stored skeleton (should never happen live; 155/155 built) → runtime blank of the raw copy, NEVER raw seeds
    dp = {"payload": copy.deepcopy(_C42_RAW), "payload_stripped": None}
    sf = _seedfree_default(dp)
    assert sf is not None
    assert _find(sf, "Welding") == [], "fallback must blank the raw seed, never ship it"


def test_grafted_container_carries_no_raw_seed():
    # the executor grafts an elided DATA container from `_default_payload`; when that default is the SEEDLESS skeleton,
    # the grafted container cannot carry the 'Welding Overlap' seed. (Independently, the graft path also blank_data_leaves
    # the raw default — this proves the source itself is clean, closing the config-chrome byte-copy / offline-replay leak.)
    seedfree_default = _seedfree_default({"payload": copy.deepcopy(_C42_RAW),
                                          "payload_stripped": copy.deepcopy(_C42_STRIPPED)})
    out = {"data": {"insight": ""}}                              # the L2 gate elided data.anomalies / data.series
    F._graft_container(out, seedfree_default, "data.anomalies")
    F._graft_container(out, seedfree_default, "data.series")
    assert _find(out, "Welding") == [], "a grafted container must NOT carry the c42 raw seed"


# ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────
#  (B) PERIOD — ctx[today|this_week|this_month] built from the run window so the reversed-CT energy fns compute
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────
_ENERGY_COLS = ["active_energy_import_kwh", "active_energy_export_kwh",
                "reactive_energy_import_kvarh", "reactive_energy_export_kvarh"]


class _StubNeuract:
    """Patch neuract.window/latest/present_columns with an in-memory monotonic counter, for the duration of a test.
    `table_cols` = the columns the fake table 'has' (absent ones pad → None, exactly like the real reader)."""

    def __init__(self, start_vals, end_vals, table_cols=None, latest_ts="2026-07-05T12:00:00+05:30"):
        self.start_vals, self.end_vals = start_vals, end_vals
        self.cols = set(table_cols if table_cols is not None else _ENERGY_COLS)
        self.latest_ts = latest_ts

    def __enter__(self):
        self._o = (nx.window, nx.latest, nx.present_columns)

        def _window(table, columns, start, end):
            first = {c: (self.start_vals.get(c) if c in self.cols else None) for c in columns}
            last = {c: (self.end_vals.get(c) if c in self.cols else None) for c in columns}
            return first, last

        def _latest(table, columns):
            return {c: (self.latest_ts if c == "timestamp_utc" else None) for c in columns}

        nx.window, nx.latest, nx.present_columns = _window, _latest, (lambda t: frozenset(self.cols))
        return self

    def __exit__(self, *a):
        nx.window, nx.latest, nx.present_columns = self._o


def test_period_deltas_built_from_window_end_anchor():
    # a monotonic forward counter: month/week/today all bound [start, run-end]; the stub returns the SAME first/last so
    # each period's delta is (end−start). active_import moved 1000→1400 → +400; reactive_import 50→90 → +40.
    with _StubNeuract(start_vals={"active_energy_import_kwh": 1000.0, "active_energy_export_kwh": 0.0,
                                  "reactive_energy_import_kvarh": 50.0, "reactive_energy_export_kvarh": 0.0},
                      end_vals={"active_energy_import_kwh": 1400.0, "active_energy_export_kwh": 0.0,
                                "reactive_energy_import_kvarh": 90.0, "reactive_energy_export_kvarh": 0.0}):
        run_window = ("2026-07-01T00:00:00+05:30", "2026-07-05T12:00:00+05:30")
        periods = F._period_deltas("gic_fake", _ENERGY_COLS, run_window)
    assert set(periods) == {"today", "this_week", "this_month"}
    for p in periods.values():
        assert p["active_import"] == 400.0
        assert p["reactive_import"] == 40.0


def test_period_delta_energy_fn_computes_a_real_value_not_blank():
    # the reactive/apparent legs are ROW-scoped (NO ∫power fallback) — before the fix they always false-blanked because
    # ctx[period] was never set. With the period ctx built, they compute the real delta.
    ctx = {"this_month": {"active_import": 375570.0, "active_export": 0.0,
                          "reactive_import": 1530.0, "reactive_export": 0.0}}
    assert E.active_energy_this_month_kwh(ctx) == 375570.0
    assert E.reactive_energy_this_month_kvarh(ctx) == 1530.0          # was None (false-blank) before the fix
    assert E.apparent_energy_this_month_kvah(ctx) is not None         # composes both legs — real, not blank


def test_reversed_ct_period_picks_the_moving_register():
    # a reversed-CT feeder: the IMPORT register is flat, the real energy is on EXPORT. _pick_register (via _period_delta)
    # must pick the mover, so the period fill is the real ~4700 kWh, not a blank.
    ctx = {"this_month": {"active_import": 0.0, "active_export": 4700.0,
                          "reactive_import": 0.0, "reactive_export": 0.0}}
    assert E.active_energy_this_month_kwh(ctx) == 4700.0


def test_period_delta_honest_blanks_when_counter_column_genuinely_absent():
    # a meter that does NOT have the reactive registers at all → those keys pad to None → the fn honest-blanks (never 0).
    with _StubNeuract(start_vals={"active_energy_import_kwh": 1000.0},
                      end_vals={"active_energy_import_kwh": 1200.0},
                      table_cols=["active_energy_import_kwh", "active_energy_export_kwh"]):   # reactive cols ABSENT
        periods = F._period_deltas("gic_fake", _ENERGY_COLS, ("2026-07-01T00:00:00+05:30",
                                                              "2026-07-05T12:00:00+05:30"))
    month = periods["this_month"]
    assert month["active_import"] == 200.0                            # present register → real delta
    assert month["reactive_import"] is None                          # genuinely-absent register → honest-blank
    assert month["reactive_export"] is None
    # and the fn that reads it degrades honestly (None, not a fabricated number)
    assert E.reactive_energy_this_month_kvarh({"this_month": month}) is None


def test_period_deltas_skipped_for_non_energy_fn():
    # generic gate: a fn that declares NO energy counter column pays nothing (no read, empty {}).
    with _StubNeuract(start_vals={}, end_vals={}):
        assert F._period_deltas("gic_fake", ["voltage_avg", "active_power_total_kw"],
                                ("2026-07-01T00:00:00+05:30", "2026-07-05T12:00:00+05:30")) == {}


def test_period_deltas_empty_table_no_anchor_degrades():
    # no run-window end AND an empty table (latest ts None) → no anchor → {} (honest-degrade, never a fabricated window).
    with _StubNeuract(start_vals={}, end_vals={}, latest_ts=None):
        assert F._period_deltas("gic_empty", _ENERGY_COLS, None) == {}


def test_period_starts_week_is_monday():
    # sanity on the calendar math: 2026-07-05 is a Sunday → week start (Monday) is 2026-06-29; month start 2026-07-01.
    anchor = datetime(2026, 7, 5, 12, 0, tzinfo=IST)
    starts = F._period_starts(anchor)
    assert starts["today"] == datetime(2026, 7, 5, 0, 0, tzinfo=IST)
    assert starts["this_week"] == datetime(2026, 6, 29, 0, 0, tzinfo=IST)   # Monday
    assert starts["this_month"] == datetime(2026, 7, 1, 0, 0, tzinfo=IST)
