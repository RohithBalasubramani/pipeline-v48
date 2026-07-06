"""Family-H render-safety fixes — pure unit tests (no DB, no host, no live model).

Covers the 2026-07-06 crash-family work:
  • ems_exec/executor/freshness.py    — freshness derived from the fill's own newest-sample age (CMD_V2 buildFreshness
                                        contract: live/stale/unknown), blank-only writes, honest no-timestamp state.
  • ems_exec/executor/trend_badge.py  — rail/trend statusBadge derived from the card's OWN bound series via CMD_V2's
                                        trendDir rule; underivable (no series) stays blank.
  • host/display_dash.py extensions   — digit-chrome restore (never a dashed formatter-DIGITS input), unit-evidence
                                        fix (a NUMBER under a `…Unit` name is a value, not a unit label), sibling
                                        rehydrate (worstVThd beside worstIThd), no-assert fallbacks (OK → '—'),
                                        and the standing guarantees (consumedHint null object untouched).
  • ems_exec/renderers/narrative_ai   — the REAL generated text threads into the CMD_V2 backendHeadline seam.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ems_exec.executor import freshness as F
from ems_exec.executor import trend_badge as T
from host import display_dash as D


def _fresh_blank():
    return {"freshness": {"status": "", "label": "", "tone": "", "lastUpdateLabel": "Last update —",
                          "title": "Live telemetry"}}


# ── freshness ────────────────────────────────────────────────────────────────────────────────────────────────────────

def test_freshness_live_from_recent_sample():
    now = datetime(2026, 7, 6, 12, 0, 0, tzinfo=timezone.utc)
    out = F.apply(_fresh_blank(), "gic_x", now=now, newest=now - timedelta(seconds=30))
    fr = out["freshness"]
    assert fr["status"] == "live" and fr["label"] == "Live" and fr["tone"] == "fail"   # fail == the red LIVE tone
    assert fr["lastUpdateLabel"].startswith("Last update ") and DASH not in fr["lastUpdateLabel"]


def test_freshness_stale_past_threshold():
    now = datetime(2026, 7, 6, 12, 0, 0, tzinfo=timezone.utc)
    out = F.apply(_fresh_blank(), "gic_x", now=now, newest=now - timedelta(minutes=10))
    fr = out["freshness"]
    assert fr["status"] == "stale" and fr["label"] == "Stale" and fr["tone"] == "warning"
    assert "ago" in fr["title"]


def test_freshness_no_timestamp_is_unknown_never_live():
    # no newest sample → the honest 'unknown/Offline/neutral' state (CMD_V2's own vocabulary), never an asserted Live
    out = F.apply(_fresh_blank(), None, newest=None)
    fr = out["freshness"]
    assert fr["status"] == "unknown" and fr["tone"] == "neutral"
    assert fr["lastUpdateLabel"] == "Last update —"


def test_freshness_never_overwrites_authored_state():
    payload = {"freshness": {"status": "stale", "label": "Stale", "tone": "warning",
                             "lastUpdateLabel": "Last update 10:00:00", "title": "t"}}
    now = datetime(2026, 7, 6, 12, 0, 0, tzinfo=timezone.utc)
    out = F.apply(payload, "gic_x", now=now, newest=now)
    assert out["freshness"]["status"] == "stale"                   # blank-only writes


# ── trend badge ──────────────────────────────────────────────────────────────────────────────────────────────────────

def _badge():
    return {"tone": "", "label": "", "dsTone": "", "vocab": {"rising": "Rising", "falling": "Falling",
                                                             "stable": "Stable"}, "key": ""}


def test_trend_badge_rising_from_series():
    out = T.apply({"trend": {"series": [100.0, 120.0], "statusBadge": _badge()}})
    b = out["trend"]["statusBadge"]
    assert (b["key"], b["tone"], b["dsTone"], b["label"]) == ("rising", "warning", "alarm", "Rising")


def test_trend_badge_stable_under_flat_threshold():
    out = T.apply({"trend": {"series": [1000.0, 1001.0], "statusBadge": _badge()}})
    assert out["trend"]["statusBadge"]["key"] == "stable"
    assert out["trend"]["statusBadge"]["dsTone"] == "normal"


def test_trend_badge_rail_header_uses_sibling_trend_series():
    # railVM.statusBadge has no own series — derives from the SIBLING trend.series (the rail contract)
    rail = {"statusBadge": {"tone": "", "label": "", "dsTone": ""},
            "trend": {"series": [200.0, 150.0], "statusBadge": _badge()}}
    out = T.apply(rail)
    assert out["statusBadge"]["key"] == "falling" and out["statusBadge"]["tone"] == "success"


def test_trend_badge_underivable_stays_blank():
    out = T.apply({"trend": {"series": [None, None], "statusBadge": _badge()}})
    assert out["trend"]["statusBadge"]["tone"] == ""               # no real endpoints → no assertion


def test_trend_badge_never_overwrites_authored_badge():
    badge = {"tone": "success", "label": "Normal", "dsTone": "normal"}
    out = T.apply({"trend": {"series": [1.0, 2.0], "statusBadge": dict(badge)}})
    assert out["trend"]["statusBadge"]["label"] == "Normal"


# ── display_dash extensions ──────────────────────────────────────────────────────────────────────────────────────────

DASH = D.DASH


def test_digit_chrome_restored_never_dashed():
    # a formatter-DIGITS input must never be '—' (Intl RangeError) — restored to the harvested default NUMBER
    payload = {"pres": {"railDecimals": None, "unit": "A", "value": None}}
    default = {"pres": {"railDecimals": 1, "unit": "A", "value": 300}}
    D.apply(payload, default)
    assert payload["pres"]["railDecimals"] == 1
    assert payload["pres"]["value"] == DASH                        # the display value still dashes


def test_digit_chrome_dict_form():
    payload = {"pres": {"decimals": {"thd": None, "pfLow": DASH}}}
    default = {"pres": {"decimals": {"thd": 1, "pfLow": 2}}}
    D.apply(payload, default)
    assert payload["pres"]["decimals"] == {"thd": 1, "pfLow": 2}


def test_number_under_unit_name_is_a_value_not_a_unit_label():
    # secKwhPerUnit (default NUMBER) must dash — the bare `…Unit` suffix must not read it as a unit label
    payload = {"data": {"secKwhPerUnit": None, "energyUnit": "kWh"}}
    default = {"data": {"secKwhPerUnit": 2.4, "energyUnit": "kWh"}}
    D.apply(payload, default)
    assert payload["data"]["secKwhPerUnit"] == DASH
    assert payload["data"]["energyUnit"] == "kWh"


def test_sibling_rehydrate_worst_objects():
    row = {"panel": "P", "iThd": 6.6, "vThd": None}
    payload = {"stats": {"worstIThd": dict(row), "worstVThd": None}}
    default = {"stats": {"worstIThd": dict(row), "worstVThd": {"panel": "Q", "iThd": 1.0, "vThd": 2.0}}}
    D.apply(payload, default)
    assert isinstance(payload["stats"]["worstVThd"], dict)         # structure restored (component derefs it)
    assert payload["stats"]["worstVThd"]["vThd"] is None           # every leaf blank — nothing asserted


def test_consumed_hint_null_object_still_untouched():
    # the standing 2026-07-03 guarantee: a legit null OBJECT with no same-length sibling stays null
    payload = {"supply": {"value": 1037.83, "unit": "kW", "consumedHint": None, "denominator": None}}
    default = {"supply": {"value": 2400, "unit": "kW", "consumedHint": {"leftKw": 1}, "denominator": 2700}}
    D.apply(payload, default)
    assert payload["supply"]["consumedHint"] is None
    assert payload["supply"]["denominator"] == DASH


def test_no_assert_fallback_driver_code():
    payload = {"pres": {"driverFallbackCode": "OK"}}
    D.apply(payload, {"pres": {"driverFallbackCode": "OK"}})
    assert payload["pres"]["driverFallbackCode"] == DASH           # absence-of-match must not assert 'OK'


def test_kvar_value_suffix_dashes():
    payload = {"sec": {"totalKvar": None, "label": "Incomers"}}
    default = {"sec": {"totalKvar": 42.0, "label": "Incomers"}}
    D.apply(payload, default)
    assert payload["sec"]["totalKvar"] == DASH


# ── narrative_ai headline threading ──────────────────────────────────────────────────────────────────────────────────

def test_narrative_emit_threads_backend_headline():
    from ems_exec.renderers.narrative_ai import _emit
    skeleton = {"summary": {"pres": {"vocab": {"a": "b"}, "backendHeadline": None}}, "widgets": {}}
    out = _emit(skeleton, {"badge": "review", "text": "Real sentence."})
    assert out["summary"]["pres"]["backendHeadline"] == "Real sentence."
    assert out["widgets"]["ai_summary"]["text"] == "Real sentence."
