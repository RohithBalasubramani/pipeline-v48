"""route-1a-timewindow — prompt→date_window extraction (offline; no LLM, no DB writes).

Contract under test:
  · layer1a.parse.window_default.clamp_window — the 1a `window` answer → a TIME_WINDOWS preset key, else None
    (the "none" sentinel, an absent/None value, or any off-vocab token all fold to None → the host keeps its default);
  · host.server._window_from_preset — a preset → a concrete {range,start,end,sampling} date_window (non-null for a real
    preset, None for None / an unknown preset) so response.date_window is non-null for a timed prompt and unchanged for
    a no-time prompt.
"""
from datetime import datetime

from layer1a.parse.window_default import clamp_window
from config.windows import TIME_WINDOWS


# ── clamp_window ──────────────────────────────────────────────────────────────────────────────────────────────────────
def test_clamp_window_accepts_real_preset():
    assert clamp_window("last-7-days") == "last-7-days"
    assert clamp_window("today") == "today"


def test_clamp_window_case_insensitive():
    assert clamp_window("Last-7-Days") == "last-7-days"
    assert clamp_window("  TODAY ") == "today"


def test_clamp_window_none_and_sentinels_fold_to_none():
    # a NO-TIME prompt → the router emits "none" (or a legacy reply omits/nulls it) → None → today/latest default kept
    assert clamp_window(None) is None
    assert clamp_window("none") is None
    assert clamp_window("null") is None
    assert clamp_window("") is None


def test_clamp_window_off_vocab_folds_to_none():
    # a range the preset vocab does not cover (e.g. 'this-month' is not a TIME_WINDOWS key) → None, never a wrong window
    assert clamp_window("this-month") is None
    assert clamp_window("last-3-fortnights") is None
    assert clamp_window(1234) is None


def test_clamp_window_vocab_is_time_windows():
    # every real TIME_WINDOWS preset survives the clamp (schema/clamp share the one vocab source)
    for k in TIME_WINDOWS:
        assert clamp_window(k) == k


# ── host._window_from_preset ──────────────────────────────────────────────────────────────────────────────────────────
def test_window_from_preset_last_7_days_is_concrete_7_day_range():
    from host.server import _window_from_preset
    w = _window_from_preset("last-7-days")
    assert w is not None
    assert w["range"] == "last-7-days"
    assert w["sampling"] == "day"                                     # TIME_WINDOWS last-7-days bucket=day → FE 'day'
    start = datetime.fromisoformat(w["start"])
    end = datetime.fromisoformat(w["end"])
    span_days = (end - start).total_seconds() / 86400.0
    assert 6.5 < span_days < 7.5                                      # a real ~7-day span, not today/latest


def test_window_from_preset_none_stays_none():
    # the no-time case: nothing to default → date_window stays None → today/latest behavior unchanged
    from host.server import _window_from_preset
    assert _window_from_preset(None) is None
    assert _window_from_preset("") is None


def test_window_from_preset_unknown_preset_is_none():
    from host.server import _window_from_preset
    assert _window_from_preset("this-month") is None                 # not a TIME_WINDOWS key → honest None (no fabrication)
