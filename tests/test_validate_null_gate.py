"""Null-gate policy + event/counter/boolean column semantics (validate/null_gate.py, 2026-07-07 user directive).
NON-LIVE — cfg is monkeypatched per test; no tunnel, no LLM. One concern: the >50%-null gate rows only.

The directive: the >50%-null check never produces verdict=fail (DB knob validate.null_gate_mode fail|warn|off,
default warn); EVENT/COUNTER/BOOLEAN-semantic columns (token vocab / boolean dtype) read NULL as 'no event' ≡ 0
for the verdict statistics; electrical quantities are NEVER coerced (a null voltage is NOT 0 V)."""
import pandas as pd

import validate.null_gate as ng
from validate.data_validate import validate_data
from validate.null_gate import is_event_semantic, coerce_event_nulls, null_gate_mode, event_semantic_tokens


def _cols(*names):
    return [{"column": n, "label": n, "kind": "raw", "unit": ""} for n in names]


def _frame(n=20, **cols):
    return pd.DataFrame({"timestamp_utc": pd.date_range("2026-07-01", periods=n, freq="min", tz="UTC")[::-1], **cols})


def _cfg_returning(overrides):
    """A fake cfg(): DB rows = `overrides`, everything else falls back to the code default (like a live miss)."""
    return lambda key, default: overrides.get(key, default)


# ---------- the vocab: event/counter/boolean semantics by NAME + DTYPE, never electrical ----------
def test_event_semantic_name_tokens():
    assert is_event_semantic("current_imbalance_event_active")     # dg_1_mfm: the 99.85%-null 12-min burst column
    assert is_event_semantic("sag_event_active")
    assert is_event_semantic("auto_restart_count")                 # counter
    assert is_event_semantic("action_flag")                        # flag
    assert is_event_semantic("interruption_event_duration_s")      # '_event_' matches anywhere (trailing '_')


def test_event_semantic_boolean_dtype():
    assert is_event_semantic("dg1_run", dtype="bool")              # boolean data_type is event-semantic regardless of name
    assert is_event_semantic("healthy", dtype="boolean")           # pandas nullable-boolean dtype string


def test_electrical_quantities_never_match():
    for col in ("voltage_avg", "current_r", "active_power_total_kw", "energy_kwh", "frequency_hz", "pf_avg"):
        assert not is_event_semantic(col, dtype="float64"), col


def test_vocab_is_db_driven_with_code_default(monkeypatch):
    """The token vocab AND the event-name pattern are INDEPENDENTLY DB-tunable: with the vocab overridden to
    ['_burst'] alone, 'sag_event_active' would still hit the pattern channel (_event_active$) -- so the pattern
    row is ALSO overridden to an inert regex, proving each channel answers only to its own row."""
    monkeypatch.setattr(ng, "cfg", _cfg_returning({"validate.event_semantic_tokens": ["_burst"],
                                                   "validation.event_name_pattern": r"_no_such_suffix$"}))
    assert event_semantic_tokens() == ["_burst"]
    assert is_event_semantic("sag_burst") and not is_event_semantic("sag_event_active")
    monkeypatch.setattr(ng, "cfg", _cfg_returning({}))             # no row -> code default
    assert event_semantic_tokens() == list(ng.DEFAULT_EVENT_TOKENS)


def test_event_name_pattern_fact_channel(monkeypatch):
    """The basket dictionary's own event-name rule (config.validation.EVENT_NAME_PATTERN, DB row
    validation.event_name_pattern) is a SEPARATE signal from the token vocab: 'thd_compliance_ieee519' carries
    NO vocab token (_event_/_count/_active/_flag) yet is a 0/1 fact flag -- the pattern channel catches it."""
    monkeypatch.setattr(ng, "cfg", _cfg_returning({}))             # no DB rows -> code defaults for BOTH channels
    assert is_event_semantic("thd_compliance_ieee519")             # pattern-only hit (absent from the token vocab)
    monkeypatch.setattr(ng, "cfg", _cfg_returning({"validate.event_semantic_tokens": ["_burst"]}))
    assert is_event_semantic("thd_compliance_ieee519")             # survives a token-vocab override -- independent channel
    monkeypatch.setattr(ng, "cfg", _cfg_returning({}))
    for col in ("voltage_avg", "active_power_total_kw"):           # electrical never matches EITHER channel
        assert not is_event_semantic(col, dtype="float64"), col


def test_malformed_pattern_row_skips_channel_never_widens(monkeypatch):
    """A fat-fingered regex row (re.error) skips the pattern channel for that call -- never a crash, never a
    widened gate; the token channel keeps working untouched."""
    monkeypatch.setattr(ng, "cfg", _cfg_returning({"validation.event_name_pattern": "(_unclosed"}))
    assert not is_event_semantic("voltage_avg", dtype="float64")   # gate stays shut on electrical
    assert not is_event_semantic("thd_compliance_ieee519")         # pattern channel skipped, token vocab has no hit
    assert is_event_semantic("sag_event_active")                   # token channel unaffected


def test_malformed_vocab_row_never_widens_gate(monkeypatch):
    """A fat-fingered DB row must honest-degrade to the code default, never blow the gate open. A bare "_burst"
    STRING (JSON string, not a list) would fan into per-char tokens ['_','b',...] and '_' then matches EVERY
    underscore-bearing column — coercing null voltage/power to 0 (the exact fabrication the directive forbids)."""
    for bad in ("_burst", {"a": 1}, 42, None, True, [], ["   "]):
        monkeypatch.setattr(ng, "cfg", _cfg_returning({"validate.event_semantic_tokens": bad}))
        assert event_semantic_tokens() == list(ng.DEFAULT_EVENT_TOKENS), bad
        assert not is_event_semantic("voltage_avg", dtype="float64"), bad   # gate stays shut on electrical
        assert not is_event_semantic("active_power_total_kw", dtype="float64"), bad


# ---------- the gate: >50%-null never fails; warn at most; DB-driven mode ----------
def test_sparse_event_column_passes_never_fails():
    """The dg_1_mfm shape: an event burst column, ~95% null over the window → PASS with an informational reason."""
    burst = [None] * 19 + [1.0]
    rep = validate_data(_frame(20, current_imbalance_event_active=burst), _cols("current_imbalance_event_active"))
    c = rep["columns"][0]
    assert c["verdict"] == "pass" and c["event_semantic"]
    assert any("no event" in r for r in c["reasons"])              # informational, names the semantics
    assert c["null_rate"] == 0.95                                  # RAW sparsity stays honest telemetry
    assert rep["summary"]["n_fail"] == 0


def test_all_null_electrical_column_warns_and_is_not_coerced():
    df = _frame(20, voltage_avg=[None] * 20)
    rep = validate_data(df, _cols("voltage_avg"))
    c = rep["columns"][0]
    assert c["verdict"] == "warn" and not c["event_semantic"]      # surfaces — never fail, never silent, never 0 V
    assert c["nonnull"] == 0 and c["null_rate"] == 1.0             # raw stats: no 0-coercion for electrical
    assert df["voltage_avg"].isna().all()                          # the frame itself is untouched
    assert rep["summary"]["n_fail"] == 0


def test_null_gate_mode_fail_restores_legacy(monkeypatch):
    monkeypatch.setattr(ng, "cfg", _cfg_returning({"validate.null_gate_mode": "fail"}))
    rep = validate_data(_frame(20, voltage_avg=[None] * 20), _cols("voltage_avg"))
    assert rep["columns"][0]["verdict"] == "fail"                  # the legacy page-blocking behavior, one DB row away


def test_null_gate_mode_off_silences_mostly_null(monkeypatch):
    monkeypatch.setattr(ng, "cfg", _cfg_returning({"validate.null_gate_mode": "off"}))
    sparse = [None] * 12 + [1.0] * 8                               # 60% null, newest rows null
    rep = validate_data(_frame(20, voltage_avg=sparse), _cols("voltage_avg"))
    c = rep["columns"][0]
    assert c["verdict"] != "fail"
    assert not any("null_rate" in r for r in c["reasons"])         # the mostly-null annotation is silent under 'off'


def test_null_gate_mode_default_and_typo_fallback(monkeypatch):
    monkeypatch.setattr(ng, "cfg", _cfg_returning({}))
    assert null_gate_mode() == "warn"                              # code default
    monkeypatch.setattr(ng, "cfg", _cfg_returning({"validate.null_gate_mode": "explode"}))
    assert null_gate_mode() == "warn"                              # a typo'd row never widens the gate


def test_absent_column_still_fails():
    rep = validate_data(_frame(20, kw=[1.0] * 20), _cols("kw", "ghost_col"))
    v = {c["column"]: c["verdict"] for c in rep["columns"]}
    assert v["kw"] == "pass" and v["ghost_col"] == "fail"          # absence is a real defect, not sparsity


# ---------- the coercion point (validate-local; the executor hook stays outside the fence) ----------
def test_coerce_event_nulls_is_copy_only():
    s = pd.Series([None, 1.0, None])
    eff = coerce_event_nulls(s)
    assert eff.isna().sum() == 0 and list(eff) == [0.0, 1.0, 0.0]
    assert s.isna().sum() == 2                                     # original series untouched
