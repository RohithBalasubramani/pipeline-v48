"""tests/test_power_plausibility_knobs.py — the POWER-derivation plausibility guards are DB-DRIVEN + GENERIC.

Three knobs that used to be bare literals in ems_exec/derivations/power.py are now app_config `power.*` rows with a
code-default mirror (db/seed_power_plausibility_knobs.sql), and each guard lives INSIDE the shared derivation fn so it
fires for EVERY metric bound to that fn on ANY asset — not one card/renderer:

  1. the energized-filter floor (power.load_factor_energized_fraction) — the SAME row the executor.rescue path reads,
     so the native load-factor mean and the rescue can never drift;
  2. the load-factor ≤ ceiling guard (power.load_factor_ceiling_pct / _ceiling_tolerance_pct) — a sign/reducer >100%
     artifact honest-blanks; caps a reversed-CT NEGATIVE series on a non-DG (UPS-style) asset;
  3. the loading-% plausibility ceiling (power.loading_plausible_max_pct) — a loading% far above physical possibility =
     a WRONG rating denominator (the 20000-vs-160 fabricated plate) → honest-blank.

PURE unit tests: cfg is monkeypatched (no DB mutation) to prove each accessor consumes its row; behavior with the code
default is asserted against the live-seeded defaults."""
from __future__ import annotations

import pytest

from ems_exec.derivations import power as P


def _series(vals):
    return {"series": [{"active_power_total_kw": v} for v in vals]}


@pytest.fixture
def patch_cfg(monkeypatch):
    """Override individual app_config keys power.py reads, falling through to the real cfg for the rest."""
    real = P._cfg

    def make(overrides):
        def fake(key, default):
            return overrides[key] if key in overrides else real(key, default)
        monkeypatch.setattr(P, "_cfg", fake)
    return make


# ── (1) accessors read their row + code-default mirror ───────────────────────────────────────────────────────────────
def test_accessors_return_code_defaults(patch_cfg):
    # with NO row (cfg returns the passed default) every accessor mirrors its documented constant
    patch_cfg({})  # no overrides, but real cfg may have live rows; assert against the code-default constants directly
    assert P._lf_energized_fraction() == P._LF_ENERGIZED_FRACTION
    assert P._lf_ceiling_pct() == P._LF_CEILING_PCT
    assert P._lf_ceiling_tolerance_pct() == P._LF_CEILING_TOLERANCE_PCT
    assert P._loading_plausible_max_pct() == P._LOADING_PLAUSIBLE_MAX_PCT


def test_accessors_clamp_bad_rows(patch_cfg):
    # a garbage / out-of-range row falls back to the code default (never propagates a nonsense knob)
    patch_cfg({"power.load_factor_energized_fraction": "oops", "power.load_factor_ceiling_pct": -5,
               "power.loading_plausible_max_pct": 0, "power.load_factor_ceiling_tolerance_pct": -1})
    assert P._lf_energized_fraction() == P._LF_ENERGIZED_FRACTION      # non-numeric → default
    assert P._lf_ceiling_pct() == P._LF_CEILING_PCT                    # <=0 → default
    assert P._loading_plausible_max_pct() == P._LOADING_PLAUSIBLE_MAX_PCT
    assert P._lf_ceiling_tolerance_pct() == P._LF_CEILING_TOLERANCE_PCT


# ── (2) load-factor ceiling — DB-driven + generic on a NON-DG reversed-CT series ─────────────────────────────────────
def test_load_factor_negative_series_caps_leq_100(patch_cfg):
    patch_cfg({})
    neg = [-185.0, -190.0, -203.0, -198.0, -180.0]   # a continuously-loaded UPS logging NEGATIVE kW (reversed-CT)
    lf = P.load_factor_pct(_series(neg))
    assert lf is not None and lf <= 100.0             # abs() → real ~94.2, never a fabricated >100
    assert lf == 94.2


def test_load_factor_ceiling_is_db_knob(patch_cfg):
    neg = [-185.0, -190.0, -203.0, -198.0, -180.0]    # real LF ~94.2
    patch_cfg({"power.load_factor_ceiling_pct": 50.0})   # lower the ceiling below the real LF
    assert P.load_factor_pct(_series(neg)) is None       # 94.2 > 50 + tol → honest-blank (knob is live + generic)


def test_energized_fraction_is_db_knob(patch_cfg):
    # a high floor strips all but the near-peak sample → fewer than min_energized → honest-blank (not a bogus 100%)
    patch_cfg({"power.load_factor_energized_fraction": 0.99})
    assert P.load_factor_pct(_series([10.0, 12.0, 500.0])) is None


# ── (3) loading-% plausibility ceiling — DB-driven + generic across assets ───────────────────────────────────────────
def test_loading_pct_plausible_fills(patch_cfg):
    patch_cfg({})
    # 207 kW on a 160-kVA-rated feeder → ~129% (a real high-but-plausible loading, under the 200% ceiling)
    assert P.kpi_kw_load_pct_of_rated({"row": {"active_power_total_kw": -207.0}, "rated_kw": 160.0}) == 129.4


def test_loading_pct_wrong_denominator_blanks(patch_cfg):
    patch_cfg({})
    # a fabricated tiny plate (rated 10) the live 207 kW exceeds 20-fold → 2070% → wrong denominator → honest-blank
    assert P.kpi_kw_load_pct_of_rated({"row": {"active_power_total_kw": -207.0}, "rated_kw": 10.0}) is None
    # the derived 0..1 ratio consumes the same guard → also blanks
    assert P.kpi_load_factor({"row": {"active_power_total_kw": -207.0}, "rated_kw": 10.0}) is None


def test_loading_pct_ceiling_is_db_knob(patch_cfg):
    # lower the ceiling to 100 → even the ~129% plausible reading now blanks (proves the knob steers the guard)
    patch_cfg({"power.loading_plausible_max_pct": 100.0})
    assert P.kpi_kw_load_pct_of_rated({"row": {"active_power_total_kw": -207.0}, "rated_kw": 160.0}) is None
