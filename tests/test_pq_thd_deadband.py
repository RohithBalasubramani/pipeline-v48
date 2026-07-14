"""tests/test_pq_thd_deadband.py -- T1-3: the thd_trend_label deadband is a DB knob, not a hardcoded +/-2.

thd_trend_label reads its 'Flat' deadband from _thd_trend_deadband_pct() -> cfg('pq.thd_trend_deadband_pct', 2.0)
(seed: db/seed_pq_thd_deadband.sql). PURE unit tests -- no DB: the module's guarded _cfg seam is monkeypatched so
the default path and the retuned path are both hermetic."""
from datetime import datetime, timedelta, timezone

from ems_exec.derivations import power_quality as PQ


IST = timezone(timedelta(hours=5, minutes=30))


def _ts(h):
    return datetime(2026, 7, 13, h, 0, 0, tzinfo=IST)


def _series(vals):
    """vals = [ithd%, ...] hourly -> the ctx series shape (single-phase THD column + ts)."""
    return [{"thd_current_r_pct": v, "ts": _ts(h)} for h, v in enumerate(vals)]


def _pin_default(monkeypatch):
    """No DB row: the guarded reader serves the caller's code default."""
    monkeypatch.setattr(PQ, "_cfg", lambda key, default: default)


def _pin_deadband(monkeypatch, value):
    def fake(key, default):
        return value if key == "pq.thd_trend_deadband_pct" else default
    monkeypatch.setattr(PQ, "_cfg", fake)


# -- default deadband (code mirror 2.0) --------------------------------------------------------------------------
def test_default_rising_on_plus_10pct_swing(monkeypatch):
    _pin_default(monkeypatch)
    # prior mean 10, recent mean 11 -> +10% swing > 2% deadband
    assert PQ.thd_trend_label({"series": _series([10.0, 10.0, 11.0, 11.0])}) == "Rising"


def test_default_falling_on_minus_10pct_swing(monkeypatch):
    _pin_default(monkeypatch)
    # prior mean 10, recent mean 9 -> -10% swing < -2% deadband
    assert PQ.thd_trend_label({"series": _series([10.0, 10.0, 9.0, 9.0])}) == "Falling"


def test_default_flat_within_deadband(monkeypatch):
    _pin_default(monkeypatch)
    # prior mean 10, recent mean 10.1 -> +1% swing, inside +/-2
    assert PQ.thd_trend_label({"series": _series([10.0, 10.0, 10.1, 10.1])}) == "Flat"
    # and the negative side: -1%
    assert PQ.thd_trend_label({"series": _series([10.0, 10.0, 9.9, 9.9])}) == "Flat"


def test_default_boundary_is_flat(monkeypatch):
    _pin_default(monkeypatch)
    # exactly +2.0% sits ON the deadband -> Flat (strict > band), characterizing the pre-knob literal's behavior
    assert PQ.thd_trend_label({"series": _series([10.0, 10.0, 10.2, 10.2])}) == "Flat"


def test_default_knob_value_is_2(monkeypatch):
    _pin_default(monkeypatch)
    assert PQ._thd_trend_deadband_pct() == 2.0


# -- DB-retuned deadband -----------------------------------------------------------------------------------------
def test_widened_deadband_50_makes_plus_10pct_flat(monkeypatch):
    _pin_deadband(monkeypatch, 50)
    # the SAME +10% swing that reads Rising by default is inside a +/-50 deadband
    assert PQ.thd_trend_label({"series": _series([10.0, 10.0, 11.0, 11.0])}) == "Flat"
    # and the falling side too
    assert PQ.thd_trend_label({"series": _series([10.0, 10.0, 9.0, 9.0])}) == "Flat"


def test_narrowed_deadband_hair_trigger(monkeypatch):
    _pin_deadband(monkeypatch, 0.5)
    # a +1% swing that reads Flat by default crosses a 0.5% deadband
    assert PQ.thd_trend_label({"series": _series([10.0, 10.0, 10.1, 10.1])}) == "Rising"


def test_garbage_knob_value_falls_back_to_code_default(monkeypatch):
    _pin_deadband(monkeypatch, "not-a-number")
    assert PQ._thd_trend_deadband_pct() == 2.0
    # behavior identical to the default path
    assert PQ.thd_trend_label({"series": _series([10.0, 10.0, 11.0, 11.0])}) == "Rising"


def test_raising_cfg_never_breaks_the_derivation(monkeypatch):
    def boom(key, default):
        raise RuntimeError("db down")
    monkeypatch.setattr(PQ, "_cfg", boom)
    assert PQ._thd_trend_deadband_pct() == 2.0
    assert PQ.thd_trend_label({"series": _series([10.0, 10.0, 11.0, 11.0])}) == "Rising"
