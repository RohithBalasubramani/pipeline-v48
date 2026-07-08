"""tests/test_card41_loss_eff_proxy.py — CARD 41 (Input vs Output Energy) single-feeder loss/eff PROXY (2026-07-07).

DEFECT: card 41's derived loss/efficiency proxy slots false-blanked — expectedLossKwh (over active_energy_import_kwh)
and lossPct (over active_power_total_kw) — as no_reading DESPITE live rows, because:
  · expected_loss_kwh needed ctx['target_efficiency_pct'] (never wired for a single feeder) → None.
  · distribution_loss_pct (the lossPct fn) needed a topology aggregate (incomers/consumers) a lone feeder lacks.
FIX: an input-vs-output card over ONE meter derives a BOUNDED design-band estimate over the meter's REAL windowed
energy/power throughput — expected_loss = window_energy × band/100, loss% = band (energy_balance.expected_loss_band_pct,
default 3.0 %). Honest proxy, never a fabrication: a genuinely-dark meter / empty window still blanks. The HV/LV-leg loss
(active_power_loss_kw/pct) stays real-or-None: it blanks a UPS/feeder that lacks the two physical HV/LV legs.

PURE unit tests — no DB, no live data (the config band falls back to its code default 3.0 with the DB absent)."""
from datetime import datetime, timedelta, timezone

from ems_exec.derivations import energy as E
from ems_exec.derivations import power as P
from ems_exec.derivations import topology as T


IST = timezone(timedelta(hours=5, minutes=30))
BAND = 3.0  # energy_balance.expected_loss_band_pct code default


def _ts(h):
    return datetime(2026, 7, 4, h, 0, 0, tzinfo=IST)


# ── expectedLossKwh: bounded design-band estimate over the meter's REAL windowed energy ──────────────────────────────
def test_expected_loss_band_fallback_fills_from_real_window_energy():
    # window energy = end−start = 1500−500 = 1000 kWh; no target_efficiency_pct → band fallback = 1000 × 3/100 = 30.
    ctx = {"start_row": {"active_energy_import_kwh": 500}, "end_row": {"active_energy_import_kwh": 1500}}
    assert E.expected_loss_kwh(ctx) == 30.0


def test_expected_loss_explicit_efficiency_still_real_exact():
    # an explicit per-asset efficiency (95 %) is unchanged: 1000 × (1 − 95/100) = 50 (the real_exact path is preserved).
    ctx = {"start_row": {"active_energy_import_kwh": 500}, "end_row": {"active_energy_import_kwh": 1500},
           "target_efficiency_pct": 95}
    assert E.expected_loss_kwh(ctx) == 50.0


def test_expected_loss_integrated_from_power_basis():
    # dead cumulative counter + live power series → window_energy integrates ∫power (100 kW × 2 h = 200 kWh), band 3 % = 6.
    ctx = {"start_row": {}, "end_row": {},
           "series": [{"active_power_total_kw": 100.0, "ts": _ts(0)}, {"active_power_total_kw": 100.0, "ts": _ts(2)}]}
    assert E.expected_loss_kwh(ctx) == 6.0


def test_expected_loss_no_energy_basis_honest_blank():
    # genuinely-dark: no counter delta AND no power series → None (never a fabricated band on an empty meter).
    assert E.expected_loss_kwh({"start_row": {}, "end_row": {}, "series": []}) is None
    assert E.expected_loss_kwh({"start_row": {}, "end_row": {}}) is None


# ── lossPct: single-feeder bounded proxy, topology aggregate when present ─────────────────────────────────────────────
def test_loss_pct_topology_aggregate_unchanged():
    # a REAL topology aggregate wins (real_exact): (Σ in − Σ out)/Σ in ×100 = (1000−950)/1000×100 = 5.0.
    ctx = {"incomers": [{"active_power_total_kw": 600}, {"active_power_total_kw": 400}],
           "consumers": [{"active_power_total_kw": 950}]}
    assert T.distribution_loss_pct(ctx) == 5.0


def test_loss_pct_topology_zero_loss():
    ctx = {"incomers": [{"active_power_total_kw": 1000}], "consumers": [{"active_power_total_kw": 1000}]}
    assert T.distribution_loss_pct(ctx) == 0.0


def test_loss_pct_single_feeder_proxy_fills_band():
    # no incomers/consumers but a real in-window series → the bounded design band (3.0 %).
    ctx = {"series": [{"active_power_total_kw": 185.0}], "row": {"active_power_total_kw": 185.0}}
    assert T.distribution_loss_pct(ctx) == BAND


def test_loss_pct_empty_window_honest_blank():
    # a window WAS scoped (series read) but carried NO sample → honest-blank, even if a clamped latest row exists.
    assert T.distribution_loss_pct({"series": [], "row": {"active_power_total_kw": 184.2}}) is None


def test_loss_pct_no_window_latest_row_basis():
    # no window scoped at all (series absent) → the latest-row reading is the basis → band.
    assert T.distribution_loss_pct({"row": {"active_power_total_kw": 185.0}}) == BAND
    # …and an empty latest row → None.
    assert T.distribution_loss_pct({"row": {}}) is None


def test_efficiency_pct_is_the_loss_complement():
    # efficiency % = 100 − loss% off the SAME basis. Single-feeder band 3.0 → 97.0.
    live = {"series": [{"active_power_total_kw": 185.0}], "row": {"active_power_total_kw": 185.0}}
    assert T.efficiency_pct(live) == 100.0 - BAND
    # topology aggregate 5.0 % loss → 95.0 % efficiency.
    agg = {"incomers": [{"active_power_total_kw": 1000}], "consumers": [{"active_power_total_kw": 950}]}
    assert T.efficiency_pct(agg) == 95.0
    # dark feeder → None (never a fabricated 100 %).
    assert T.efficiency_pct({"series": [], "row": {}}) is None


def test_ai_loss_summary_tracks_the_proxy():
    # the narrative fn composes on the SAME proxy → real text on a live feeder, honest-blank on a dark one.
    live = {"series": [{"active_power_total_kw": 185.0}], "row": {"active_power_total_kw": 185.0}}
    assert isinstance(T.ai_loss_summary(live), str) and "%" in T.ai_loss_summary(live)
    assert T.ai_loss_summary({"series": [], "row": {}}) is None


# ── HV/LV-leg loss stays honest: a genuinely-absent input leg still blanks (NO over-fill) ─────────────────────────────
def test_hv_lv_leg_loss_blanks_without_both_legs():
    # gic_* UPS/feeder tables carry NO hv_input_kw / lv_output_kw column → these correctly honest-blank.
    assert P.active_power_loss_kw({"row": {"active_power_total_kw": 185.0}}) is None
    assert P.active_power_loss_pct({"row": {"active_power_total_kw": 185.0}}) is None
    # both legs present → the real input−output loss computes.
    assert P.active_power_loss_kw({"row": {"hv_input_kw": 500.0, "lv_output_kw": 470.0}}) == 30.0
