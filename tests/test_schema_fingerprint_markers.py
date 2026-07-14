"""tests/test_schema_fingerprint_markers.py -- T1-5: the fingerprint MARKER columns are a DB json row with the
_MARK_* constants as the code-default mirror.

_classify discriminates by _markers() -> cfg('grounding.fingerprint_markers', None) (seed:
db/seed_schema_fingerprint_markers.sql); a dict row overlays per-key, anything else serves _MARKER_DEFAULTS.
PURE unit tests -- no DB: cfg is monkeypatched at its home (config.app_config), which _markers() re-imports at
call time, so both the default path and the overlay path are hermetic."""
import config.app_config as AC
from grounding import schema_fingerprint as SF


def _pin_absent_row(monkeypatch):
    """No grounding.fingerprint_markers row: cfg serves the caller's default (None)."""
    monkeypatch.setattr(AC, "cfg", lambda key, default: default)


def _pin_row(monkeypatch, row):
    def fake(key, default):
        return row if key == "grounding.fingerprint_markers" else default
    monkeypatch.setattr(AC, "cfg", fake)


# -- default parity: all five shapes classify exactly as the pre-knob constants did -------------------------------
def test_default_tm_ups_by_output_power(monkeypatch):
    _pin_absent_row(monkeypatch)
    assert SF._classify({"timestamp_utc", "output_active_power_total_kw"}) == SF.TM_UPS_56


def test_default_tm_ups_by_battery_pct(monkeypatch):
    _pin_absent_row(monkeypatch)
    assert SF._classify({"timestamp_utc", "battery_backup_pct"}) == SF.TM_UPS_56


def test_default_feedbacks_by_breaker_flag(monkeypatch):
    _pin_absent_row(monkeypatch)
    assert SF._classify({"timestamp_utc", "bc_acb_on_fb", "tf_1_winding_temperature"}) == SF.FEEDBACKS_35


def test_default_p1_by_std_power_plus_harmonic5(monkeypatch):
    _pin_absent_row(monkeypatch)
    assert SF._classify({"timestamp_utc", "active_power_total_kw", "harmonic_5th_pct"}) == SF.P1_72


def test_default_ng_se_jk_by_std_power_without_harmonic5(monkeypatch):
    _pin_absent_row(monkeypatch)
    assert SF._classify({"timestamp_utc", "active_power_total_kw"}) == SF.NG_SE_JK_70


def test_default_sch_stub_when_no_marker_matches(monkeypatch):
    _pin_absent_row(monkeypatch)
    assert SF._classify({"timestamp_utc", "spare_1"}) == SF.SCH_STUB
    assert SF._classify(set()) == SF.SCH_STUB


def test_default_specificity_order(monkeypatch):
    _pin_absent_row(monkeypatch)
    # UPS naming beats breaker beats standard power (most-specific first)
    both = {"output_active_power_total_kw", "bc_acb_on_fb", "active_power_total_kw", "harmonic_5th_pct"}
    assert SF._classify(both) == SF.TM_UPS_56
    assert SF._classify({"bc_acb_on_fb", "active_power_total_kw"}) == SF.FEEDBACKS_35


def test_marker_defaults_mirror_the_constants(monkeypatch):
    _pin_absent_row(monkeypatch)
    assert SF._markers() == {
        "ups_power": SF._MARK_UPS_POWER,
        "ups_batt": SF._MARK_UPS_BATT,
        "breaker": SF._MARK_BREAKER,
        "std_power": SF._MARK_STD_POWER,
        "harmonic5": SF._MARK_HARMONIC5,
    } == SF._MARKER_DEFAULTS
    # a fresh copy each call: mutating the result never poisons the code-default mirror
    mk = SF._markers()
    mk["harmonic5"] = "mutated"
    assert SF._MARKER_DEFAULTS["harmonic5"] == SF._MARK_HARMONIC5
    assert SF._markers()["harmonic5"] == SF._MARK_HARMONIC5


# -- DB overlay: rerouting ONE marker changes the classification --------------------------------------------------
def test_override_reroutes_harmonic5_marker(monkeypatch):
    _pin_row(monkeypatch, {"harmonic5": "my_alt_harmonic_col"})
    # the old marker column no longer proves p1_72 -> the same column set now reads ng_se_jk_70
    assert SF._classify({"active_power_total_kw", "harmonic_5th_pct"}) == SF.NG_SE_JK_70
    # the rerouted marker column DOES prove p1_72
    assert SF._classify({"active_power_total_kw", "my_alt_harmonic_col"}) == SF.P1_72
    # the four untouched markers keep their code defaults (per-key fallback)
    assert SF._classify({"output_active_power_total_kw"}) == SF.TM_UPS_56
    assert SF._classify({"bc_acb_on_fb"}) == SF.FEEDBACKS_35


def test_override_blank_value_falls_back_per_key(monkeypatch):
    _pin_row(monkeypatch, {"breaker": "", "harmonic5": None})
    mk = SF._markers()
    assert mk["breaker"] == SF._MARK_BREAKER
    assert mk["harmonic5"] == SF._MARK_HARMONIC5


def test_non_dict_row_serves_defaults(monkeypatch):
    _pin_row(monkeypatch, ["not", "a", "dict"])
    assert SF._markers() == SF._MARKER_DEFAULTS


def test_empty_dict_row_serves_defaults(monkeypatch):
    _pin_row(monkeypatch, {})
    assert SF._markers() == SF._MARKER_DEFAULTS


def test_raising_cfg_serves_defaults(monkeypatch):
    def boom(key, default):
        raise RuntimeError("db down")
    monkeypatch.setattr(AC, "cfg", boom)
    assert SF._markers() == SF._MARKER_DEFAULTS
    assert SF._classify({"active_power_total_kw", "harmonic_5th_pct"}) == SF.P1_72
