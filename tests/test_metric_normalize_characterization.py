"""tests/test_metric_normalize_characterization.py — pins TODAY'S (legacy) behavior of config/metrics.py
normalize_metric BEFORE the Tier-0 strict mode (deterministic_audit_20260714 F1-nm / L1A-4 / T0-6).

Pins the CORRECT exact-match tiers (vocab word; alias phrase) AND the substring-loop defects strict mode retires:
  · ORDER-DEPENDENCE: the vocab loop runs before the alias loop, so 'power factor trend' hits vocab 'power'
    INSIDE the phrase before the alias 'power factor'→'pf' can — the phrase's true metric is pf.
  · SILENT DEFAULT: an off-vocab metric ('xyzzy') silently returns the default with no telemetry.
Uses code defaults via monkeypatched cfg (the live DB row differs — 14 metrics vs code's 8)."""
import pytest

import config.metrics as M


@pytest.fixture(autouse=True)
def _code_defaults(monkeypatch):
    # pin cfg to code defaults so the characterization is stable regardless of live DB rows
    monkeypatch.setattr("config.metrics.cfg", lambda key, default=None: default)


def test_exact_vocab_word():
    assert M.normalize_metric("voltage") == "voltage"
    assert M.normalize_metric("  THD ") == "thd"          # strip + lower


def test_exact_alias_phrase():
    assert M.normalize_metric("power factor") == "pf"
    assert M.normalize_metric("harmonics") == "thd"
    assert M.normalize_metric("kwh") == "energy"


def test_empty_is_default():
    assert M.normalize_metric("") == "power"
    assert M.normalize_metric(None) == "power"


# ── the substring-loop behaviors strict mode retires ─────────────────────────────────────────────────────────────────

def test_DEFECT_vocab_substring_beats_alias():
    # 'power factor trend' contains vocab 'power' → the vocab loop wins before the alias 'power factor'→'pf'
    assert M.normalize_metric("power factor trend") == "power"


def test_vocab_substring_in_phrase():
    assert M.normalize_metric("voltage fluctuation") == "voltage"


def test_alias_substring_in_phrase():
    # no vocab word inside, alias key 'amps' is → current
    assert M.normalize_metric("amps trend") == "current"


def test_DEFECT_silent_default_on_no_match():
    # off-vocab metric silently collapses to the default with no telemetry (strict mode adds metric_unresolved)
    assert M.normalize_metric("xyzzy") == "power"
