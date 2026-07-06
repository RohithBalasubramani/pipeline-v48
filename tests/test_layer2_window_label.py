"""EMIT WINDOW/LABEL COHERENCE [c14 'Monthly'+range=this-month over a 24h fill; c16 declared last-7-days beside a
24h-backfilled window — fullsweep_20260706_004334 v18_03]. Two seams, both deterministic + DB-policy-driven
(db/seed_emit_coherence.sql, code-default mirrors):

  (a) layer2/coherence.reconcile_window_labels — a period-declaring metadata leaf (periodLabel / range) that names a
      DIFFERENT period family than the fill window is morphed to the window truth (policy 'morph', default) or
      blanked; option-picker chrome and unclassified labels are never touched.
  (b) layer2/build._backfill_default_window — the AI's OWN declared range (window.lookback / ems_backend.range) now
      drives the backfilled window bounds, so declared range == fill window by construction.

Hermetic: cfg pinned to code defaults. All non-live, deterministic."""
import pytest

import layer2.coherence as coh
from layer2.coherence import reconcile_window_labels, fill_family
from layer2.build import _backfill_default_window, _range_delta


@pytest.fixture(autouse=True)
def _pinned_cfg(monkeypatch):
    monkeypatch.setattr(coh, "cfg", lambda key, default: default)     # code-default mirrors (DB rows are exact copies)
    yield


_DI_24H = {"window": {"start": "2026-07-04T19:34:43+00:00", "end": "2026-07-05T19:34:43+00:00",
                      "backfill": {"origin": "default_range", "range": "last-24h", "anchor": "wall_clock"}},
           "consumer": {"range": None}}


def test_c14_monthly_label_and_this_month_range_morph_to_the_24h_fill_truth():
    """The exact c14 shape: exact_metadata periodLabel='Monthly' + card.range='this-month' while the backfilled fill
    window is last-24h → BOTH leaves morph to the window truth; the rangeOptions picker list is untouched chrome."""
    em = {"card": {"view": {"periodLabel": "Monthly",
                            "rangeOptions": [{"label": "This month", "value": "this-month"},
                                             {"label": "Today", "value": "today"}]},
                   "range": "this-month", "sampling": "hourly"}}
    out = reconcile_window_labels(em, _DI_24H)
    assert em["card"]["view"]["periodLabel"] == "Last 24h"            # label morphs to windows.range_labels truth
    assert em["card"]["range"] == "last-24h"                          # range-value leaf morphs to the fill token
    assert em["card"]["view"]["rangeOptions"][0]["label"] == "This month"   # picker options never touched
    assert em["card"]["sampling"] == "hourly"                         # non-period keys untouched
    assert len(out) == 2 and all("fill window" in w["reason"] for w in out)


def test_agreeing_and_unclassified_labels_never_touched():
    em = {"card": {"view": {"periodLabel": "Today"}, "range": "today", "status": "Live"}}
    di = {"window": {"backfill": {"range": "today"}}, "consumer": {"range": "today"}}
    assert reconcile_window_labels(em, di) == []
    assert em["card"]["view"]["periodLabel"] == "Today"
    em2 = {"card": {"view": {"periodLabel": "Live rolling"}}}         # unclassified label = compatible, never flags
    assert reconcile_window_labels(em2, _DI_24H) == []


def test_blank_policy_and_off_policy(monkeypatch):
    em = {"view": {"periodLabel": "Monthly"}}
    monkeypatch.setattr(coh, "cfg", lambda k, d: "blank" if k == "gates.window_label_policy" else d)
    out = reconcile_window_labels(em, _DI_24H)
    assert em["view"]["periodLabel"] == "" and len(out) == 1          # blanked, with a reason
    em2 = {"view": {"periodLabel": "Monthly"}}
    monkeypatch.setattr(coh, "cfg", lambda k, d: "off" if k == "gates.window_label_policy" else d)
    assert reconcile_window_labels(em2, _DI_24H) == []
    assert em2["view"]["periodLabel"] == "Monthly"


def test_fill_family_from_span_when_range_token_unclassified():
    """No classifiable range token → the window start/end SPAN buckets the family; an in-between span never flags."""
    di = {"window": {"start": "2026-06-28T00:00:00+00:00", "end": "2026-07-05T00:00:00+00:00"}}
    assert fill_family(di)[0] == "week"
    di_odd = {"window": {"start": "2026-07-01T00:00:00+00:00", "end": "2026-07-04T12:00:00+00:00"}}   # 3.5 days
    assert fill_family(di_odd)[0] is None
    assert reconcile_window_labels({"periodLabel": "Monthly"}, di_odd) == []   # unresolvable fill → never flags


def test_c16_declared_last_7_days_drives_the_backfilled_window():
    """The exact c16 shape: window {lookback:'last-7-days', sampling:'hourly'} with no bounds — the backfill now
    resolves the DECLARED range (7 days), not the DB default 24h, so the fill window agrees with the consumer range."""
    di = {"window": {"lookback": "last-7-days", "sampling": "hourly", "time_mode": "choice"},
          "ems_backend": {"endpoint": "energy-power-history", "range": "last-7-days", "sampling": "hourly"}}
    note = _backfill_default_window(di, None)
    w = di["window"]
    assert w["backfill"]["origin"] == "declared_range" and w["backfill"]["range"] == "last-7-days"
    from datetime import datetime
    span = datetime.fromisoformat(w["end"]) - datetime.fromisoformat(w["start"])
    assert abs(span.total_seconds() - 7 * 86400) < 60
    assert "declared_range" in note


def test_declared_month_and_unparseable_ranges():
    assert _range_delta("this-month").days == 30
    assert _range_delta("last-30-days").days == 30
    assert _range_delta("today").days == 1
    assert _range_delta("gibberish") is None                          # → DB default range decides (unchanged behavior)
    di = {"window": {"lookback": "gibberish"}}
    _backfill_default_window(di, None)
    assert di["window"]["backfill"]["origin"] == "default_range"


def test_ai_explicit_bounds_still_win():
    di = {"window": {"start": "2026-07-01T00:00:00", "end": "2026-07-02T00:00:00", "lookback": "last-7-days"}}
    assert _backfill_default_window(di, None) is None                 # AI-authored bounds honored untouched
    assert di["window"]["start"] == "2026-07-01T00:00:00"
