"""tests/test_metrics_normalize_strict.py - T0-6 strict metric normalization (metrics.normalize_strict flag).

Flag OFF (default): normalize_metric is BYTE-IDENTICAL legacy (substring loops run; 'power factor trend' -> 'power');
matches record NO telemetry, only the terminal fall-through does (both modes - telemetry only).
Flag ON: exact vocab + exact alias only; any fallthrough returns the default AND records obs.failures
metric_unresolved (stage 'metric_normalize'). metric_hint is the word-boundary scan (longest alias key first;
'empower the team' must NOT hit 'power'); prompt_metric_hint is the 1b basket one-liner over both modes.
Pins code defaults via monkeypatched cfg (mirrors test_metric_normalize_characterization.py)."""
import pytest

import config.metrics as M


@pytest.fixture(autouse=True)
def _code_defaults(monkeypatch):
    # pin cfg to code defaults so the assertions are stable regardless of live DB rows
    monkeypatch.setattr("config.metrics.cfg", lambda key, default=None: default)


@pytest.fixture
def recorded(monkeypatch):
    """Capture obs.failures.record calls (normalize_metric resolves the attribute at call time)."""
    calls = []

    def fake_record(stage, reason, **kw):
        calls.append({"stage": stage, "reason": reason, **kw})
        return {}

    monkeypatch.setattr("obs.failures.record", fake_record)
    return calls


def _set_flag(monkeypatch, on):
    """Fake config.app_config.flag_on for the strict key only (normalize_metric imports it lazily)."""
    monkeypatch.setattr(
        "config.app_config.flag_on",
        lambda key, default=False, cfg_fn=None: on if key == "metrics.normalize_strict" else default)


# -- flag OFF: legacy byte-identical, no telemetry on any match -------------------------------------------------------

def test_off_substring_legacy_and_silent_on_matches(monkeypatch, recorded):
    _set_flag(monkeypatch, False)
    assert M.normalize_metric("power factor trend") == "power"   # vocab-substring beats alias (legacy defect, pinned)
    assert M.normalize_metric("voltage fluctuation") == "voltage"
    assert M.normalize_metric("amps trend") == "current"         # alias-substring tier
    assert M.normalize_metric("pf") == "pf"
    assert M.normalize_metric("power factor") == "pf"
    assert recorded == []                                        # matches never record


def test_off_terminal_fallthrough_records(monkeypatch, recorded):
    _set_flag(monkeypatch, False)
    assert M.normalize_metric("xyzzy") == "power"                # legacy silent default, now with telemetry
    assert len(recorded) == 1
    assert recorded[0]["stage"] == "metric_normalize"
    assert recorded[0]["reason"] == "metric_unresolved"
    assert recorded[0]["detail"] == "xyzzy"


# -- flag ON: exact-only, fallthrough = default + metric_unresolved ---------------------------------------------------

def test_on_phrase_falls_to_default_and_records(monkeypatch, recorded):
    _set_flag(monkeypatch, True)
    assert M.normalize_metric("power factor trend") == "power"   # the DEFAULT, not the substring hit
    assert [(c["stage"], c["reason"]) for c in recorded] == [("metric_normalize", "metric_unresolved")]
    assert recorded[0]["detail"] == "power factor trend"


def test_on_vocab_substring_no_longer_matches(monkeypatch, recorded):
    _set_flag(monkeypatch, True)
    assert M.normalize_metric("voltage fluctuation") == "power"  # legacy said 'voltage'; strict = default + telemetry
    assert len(recorded) == 1
    assert recorded[0]["reason"] == "metric_unresolved"


def test_on_exact_tiers_unchanged_and_silent(monkeypatch, recorded):
    _set_flag(monkeypatch, True)
    assert M.normalize_metric("pf") == "pf"                      # exact vocab word
    assert M.normalize_metric("power factor") == "pf"            # exact alias phrase
    assert M.normalize_metric("  THD ") == "thd"                 # strip + lower still applies
    assert recorded == []                                        # exact matches never record


def test_on_empty_is_default_and_silent(monkeypatch, recorded):
    _set_flag(monkeypatch, True)
    assert M.normalize_metric("") == "power"
    assert M.normalize_metric(None) == "power"
    assert recorded == []                                        # empty input is not an unresolved metric


# -- metric_hint: word-boundary scan, longest alias key first ---------------------------------------------------------

def test_metric_hint_word_boundary_alias():
    assert M.metric_hint("show volts for pcc-1") == "voltage"


def test_metric_hint_no_substring_false_positive():
    assert M.metric_hint("empower the team") is None             # 'power' inside 'empower' must NOT hit


def test_metric_hint_longest_alias_first():
    # 'total harmonic distortion' (-> thd) must win over its shorter contained aliases
    assert M.metric_hint("total harmonic distortion trend") == "thd"


def test_metric_hint_correct_phrase_precedence():
    assert M.metric_hint("power factor trend") == "pf"           # alias phrase beats bare vocab 'power'


def test_metric_hint_vocab_word():
    assert M.metric_hint("plot voltage for the incomer") == "voltage"


def test_metric_hint_none_on_no_hit():
    assert M.metric_hint("xyzzy") is None
    assert M.metric_hint("") is None
    assert M.metric_hint(None) is None


# -- prompt_metric_hint: the 1b basket one-liner, both modes ----------------------------------------------------------

def test_prompt_metric_hint_flag_off_is_legacy(monkeypatch, recorded):
    _set_flag(monkeypatch, False)
    assert M.prompt_metric_hint("power factor trend") == "power"   # byte-identical legacy path
    assert M.prompt_metric_hint("empower the team") == "power"     # legacy substring 'power' inside 'empower'
    assert recorded == []


def test_prompt_metric_hint_flag_on_uses_hint(monkeypatch, recorded):
    _set_flag(monkeypatch, True)
    assert M.prompt_metric_hint("power factor trend") == "pf"      # metric_hint wins, no telemetry
    assert recorded == []
    assert M.prompt_metric_hint("empower the team") == "power"     # no hint -> normalize_metric default + telemetry
    assert [(c["stage"], c["reason"]) for c in recorded] == [("metric_normalize", "metric_unresolved")]
