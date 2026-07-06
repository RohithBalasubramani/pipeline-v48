"""tests/test_energy_from_power.py — F4 dead-counter kWh recovery (∫power).

The 4 cumulative energy-counter registers (active/reactive import/export kWh) are all-NULL on many meters, while
active_power_total_kw logs continuously. Energy IS ∫P dt, so kWh is RECOVERABLE by trapezoidally integrating the observed
power series over the window (fidelity real_approx, honest note 'integrated from power'). These are PURE unit tests — no
DB, no live data (the neuract series() reader is monkeypatched)."""
from datetime import datetime, timedelta, timezone

from ems_exec.derivations import energy as E
from ems_exec.derivations import registry as R


IST = timezone(timedelta(hours=5, minutes=30))


def _ts(h):
    return datetime(2026, 7, 4, h, 0, 0, tzinfo=IST)


def _series(pairs, col="active_power_total_kw"):
    """pairs = [(hour, power), ...] → the series ctx-row shape {col: value, ts: datetime}."""
    return [{col: p, "ts": _ts(h)} for (h, p) in pairs]


# ── (1) trapezoidal integration, reversed-CT aware ──────────────────────────────────────────────────────────────────
def test_flat_power_is_power_times_hours():
    # 100 kW held flat for 3 h → 300 kWh (trapezoid of a constant = rectangle).
    ctx = {"series": _series([(12, 100.0), (13, 100.0), (14, 100.0), (15, 100.0)])}
    assert E.energy_from_power_kwh(ctx) == 300.0


def test_trapezoid_of_a_ramp():
    # power ramps 0→200 kW over 2 h → ∫ = trapezoids: (0+100)/2 + (100+200)/2 = 50 + 150 = 200 kWh.
    ctx = {"series": _series([(12, 0.0), (13, 100.0), (14, 200.0)])}
    assert E.energy_from_power_kwh(ctx) == 200.0


def test_reversed_ct_negative_power_is_abs():
    # a reversed-CT feeder logs NEGATIVE power; consumption is a magnitude → integrate |power|.
    ctx = {"series": _series([(12, -500.0), (13, -500.0)])}
    assert E.energy_from_power_kwh(ctx) == 500.0
    # sign-mixed points still integrate their magnitudes
    ctx2 = {"series": _series([(12, -100.0), (13, 100.0)])}
    assert E.energy_from_power_kwh(ctx2) == 100.0


def test_reactive_twin_reads_reactive_column():
    ctx = {"series": _series([(12, 60.0), (13, 60.0)], col="reactive_power_total_kvar")}
    assert E.reactive_energy_from_power_kvarh(ctx) == 60.0


def test_iso_string_timestamps_also_parse():
    # ts may arrive as an ISO string (not just a datetime) — still integrable.
    ctx = {"series": [
        {"active_power_total_kw": 100.0, "ts": "2026-07-04T12:00:00+05:30"},
        {"active_power_total_kw": 100.0, "ts": "2026-07-04T14:00:00+05:30"},
    ]}
    assert E.energy_from_power_kwh(ctx) == 200.0


# ── (2) honest-degrade — never fabricate, never NaN ─────────────────────────────────────────────────────────────────
def test_single_sample_degrades():
    assert E.energy_from_power_kwh({"series": _series([(12, 100.0)])}) is None


def test_empty_series_degrades():
    assert E.energy_from_power_kwh({"series": []}) is None
    assert E.energy_from_power_kwh({}) is None


def test_none_power_samples_dropped_then_degrade():
    # every power sample None → nothing to integrate → honest None (not 0, not NaN).
    ctx = {"series": _series([(12, None), (13, None)])}
    assert E.energy_from_power_kwh(ctx) is None


def test_non_positive_elapsed_degrades():
    # two samples at the SAME instant → no elapsed time → honest None (never ÷0).
    ctx = {"series": [
        {"active_power_total_kw": 100.0, "ts": _ts(12)},
        {"active_power_total_kw": 200.0, "ts": _ts(12)},
    ]}
    assert E.energy_from_power_kwh(ctx) is None


# ── (3) the dead-counter FALLBACK on the existing windowed-delta energy fns ─────────────────────────────────────────
def test_window_energy_prefers_live_counter():
    # counters present → real_exact windowed delta, NOT the integral.
    ctx = {"start_row": {"active_energy_import_kwh": 100.0},
           "end_row": {"active_energy_import_kwh": 250.5},
           "series": _series([(12, 9999.0), (13, 9999.0)])}   # a series the fn must IGNORE while counters live
    assert E.window_energy_kwh(ctx) == 150.5


def test_window_energy_falls_back_to_integration_when_counter_dead():
    ctx = {"start_row": {"active_energy_import_kwh": None},
           "end_row": {"active_energy_import_kwh": None},
           "series": _series([(12, 100.0), (13, 100.0), (14, 100.0)])}
    assert E.window_energy_kwh(ctx) == 200.0


def test_todays_total_falls_back_to_integration():
    ctx = {"start_row": {"active_energy_import_kwh": None, "reactive_energy_import_kvarh": None},
           "end_row": {"active_energy_import_kwh": None, "reactive_energy_import_kvarh": None},
           "series": _series([(12, 500.0), (13, 500.0)])}
    assert E.todays_energy_total_kwh(ctx) == 500.0


def test_period_delta_fns_fall_back_to_integration():
    # ctx['today'|'this_week'|'this_month'] deltas absent (the per-card executor never builds them) → integrate.
    ctx = {"series": _series([(12, 250.0), (14, 250.0)])}   # 250 kW × 2 h = 500 kWh
    assert E.active_energy_today_kwh(ctx) == 500.0
    assert E.active_energy_this_week_kwh(ctx) == 500.0
    assert E.active_energy_this_month_kwh(ctx) == 500.0


def test_period_delta_prefers_live_register():
    # a live reversed-CT export register present → windowed delta wins over the integral.
    ctx = {"today": {"active_import": 0.0, "active_export": 321.0},
           "series": _series([(12, 9999.0), (13, 9999.0)])}
    assert E.active_energy_today_kwh(ctx) == 321.0


# ── (4) registry dispatch: expression-degrade FALLS THROUGH to the python fn (∫power recovery) ──────────────────────
def test_registry_expression_degrade_falls_through_to_fn(monkeypatch):
    # windowEnergyKwh's DB expression reads the (dead) counter → evaluates None; the python fn then RECOVERS via ∫power.
    monkeypatch.setattr(R, "_expression_for",
                        lambda k: "round(max(end.active_energy_import_kwh - start.active_energy_import_kwh, 0), 1)")
    ctx = {"start_row": {"active_energy_import_kwh": None},
           "end_row": {"active_energy_import_kwh": None},
           "row": {},
           "series": _series([(12, 100.0), (13, 100.0), (14, 100.0)])}
    assert R.run("windowEnergyKwh", ctx) == 200.0


def test_registry_expression_wins_when_it_produces_a_value(monkeypatch):
    # a live counter → the expression yields a real number and is authoritative (fn NOT consulted).
    monkeypatch.setattr(R, "_expression_for",
                        lambda k: "round(max(end.active_energy_import_kwh - start.active_energy_import_kwh, 0), 1)")
    ctx = {"start_row": {"active_energy_import_kwh": 100.0},
           "end_row": {"active_energy_import_kwh": 250.5},
           "row": {},
           "series": _series([(12, 9999.0), (13, 9999.0)])}
    assert R.run("windowEnergyKwh", ctx) == 150.5


def test_registry_energy_from_power_value_key(monkeypatch):
    monkeypatch.setattr(R, "_expression_for", lambda k: None)  # no expression row → python fn
    ctx = {"series": _series([(12, 100.0), (13, 100.0)])}
    assert R.run("energyFromPowerKwh", ctx) == 100.0


# ── (5) the neuract series() reader drops fully-dead buckets (NULL-safe integrand) ──────────────────────────────────
def test_neuract_series_drops_all_null_buckets(monkeypatch):
    from ems_exec.data import neuract as nx
    monkeypatch.setattr(nx, "_existing", lambda t, cols: (["active_power_total_kw"], []))
    # bucket rows: (ts, power) — the middle bucket is a dead gap (NULL) and must be DROPPED, not integrated as 0.
    monkeypatch.setattr(nx, "_run", lambda sql, params=None: [
        (_ts(12), -100.0), (_ts(13), None), (_ts(14), -100.0)])
    out = nx.series("some_table", ["active_power_total_kw"], "2026-07-04", "2026-07-05")
    assert [r["active_power_total_kw"] for r in out] == [-100.0, -100.0]
    assert all("ts" in r for r in out)
