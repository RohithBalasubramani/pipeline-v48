"""statutory_band per-class deviation (hardcoding F3 follow-up, CMD_V2 parity — owner call 2026-07-12).

The band's deviation % resolves PER-CLASS (asset_class_default.voltage_statutory_deviation_pct: DG=5.0, others 10.0
— ports backend2 config_defaults.py) via ctx.asset_table → nameplate category, falling back to the
derivation.statutory_band_pct knob (10.0) when the ctx carries no resolvable asset. Deterministic: nameplate +
class-default reads are monkeypatched (no DB)."""
import pytest

from ems_exec.derivations import voltage as V


ROW = {"voltage_avg": 240.0, "kpi_voltage_deviation_pct": 0.0}   # nominal recovers to exactly 240.0


@pytest.fixture
def classed(monkeypatch):
    """Pin the nameplate category + class defaults so the test never touches the DB."""
    from config import nameplates as np
    from config import asset_class_defaults as acd
    monkeypatch.setattr(np, "get_nameplate",
                        lambda t: {"asset_category": {"dg_1_mfm": "DG", "tx_1": "Transformer"}.get(t)})
    monkeypatch.setattr(acd, "class_field",
                        lambda cat, field, default=None: ({"DG": 5.0, "Transformer": 10.0}.get(cat, default)
                                                          if field == "voltage_statutory_deviation_pct" else default))


def test_dg_band_is_class_tightened(classed):
    band = V.statutory_band({"row": ROW, "asset_table": "dg_1_mfm"})
    assert band == {"min": 228.0, "max": 252.0, "nominal": 240.0}          # ±5% — the DG class policy


def test_non_dg_band_stays_ten_pct(classed):
    band = V.statutory_band({"row": ROW, "asset_table": "tx_1"})
    assert band == {"min": 216.0, "max": 264.0, "nominal": 240.0}          # ±10% — unchanged for other classes


def test_no_table_falls_back_to_knob_default(classed):
    band = V.statutory_band({"row": ROW})                                   # no asset in ctx → knob/code default 10.0
    assert band == {"min": 216.0, "max": 264.0, "nominal": 240.0}


def test_unknown_class_falls_back(classed):
    band = V.statutory_band({"row": ROW, "asset_table": "mystery_meter"})   # nameplate misses → category None
    assert band == {"min": 216.0, "max": 264.0, "nominal": 240.0}
