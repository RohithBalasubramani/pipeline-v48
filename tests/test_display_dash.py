"""host/display_dash.py — the serve-boundary HONEST-DASH policy (pure unit tests, no DB, no host).

Covers the 2026-07-03 mechanism-gap fix: unit-adjacency is a SUFFIX vocabulary (app_config
display.unit_sibling_suffixes, code default ["unit"]) so camelCase unit-like siblings (percentUnit / valueUnit) also
prove a display object — a scalar null beside one is dashed instead of crashing an unguarded fmt(null) site. The type
proof stands: only a null whose DEFAULT payload holds a scalar at the same path is dashed; a legitimately-null OBJECT
(supply.consumedHint) is never touched."""
from __future__ import annotations

from host import display_dash as D


def test_dash_literal_unit_sibling():
    payload = {"tile": {"label": "Voltage", "value": None, "unit": "V"}}
    default = {"tile": {"label": "Voltage", "value": 239.4, "unit": "V"}}
    D.apply(payload, default)
    assert payload["tile"]["value"] == D.DASH
    assert payload["tile"]["unit"] == "V"                      # the unit key itself is never dashed


def test_dash_unitlike_suffix_sibling():
    # percentUnit is unit-LIKE (suffix vocabulary) — the null display scalars beside it dash (the fmt(null) crash gap)
    payload = {"hint": {"leftKw": None, "consumedPct": None, "percentUnit": "%", "leftLabel": "left"}}
    default = {"hint": {"leftKw": 1663, "consumedPct": 38, "percentUnit": "%", "leftLabel": "left"}}
    D.apply(payload, default)
    assert payload["hint"]["leftKw"] == D.DASH
    assert payload["hint"]["consumedPct"] == D.DASH
    assert payload["hint"]["percentUnit"] == "%"


def test_null_object_never_dashed():
    # a whole-object null (consumedHint:null — the honest omit) is NOT a display scalar: the default proves a DICT there
    payload = {"supply": {"value": 1037.83, "unit": "kW", "consumedHint": None, "denominator": None}}
    default = {"supply": {"value": 2400, "unit": "kW", "consumedHint": {"leftKw": 1}, "denominator": 2700}}
    D.apply(payload, default)
    assert payload["supply"]["consumedHint"] is None           # object null survives (hasConsumedHint guard hides row)
    assert payload["supply"]["denominator"] == D.DASH          # scalar null beside unit → the honest dash


def test_no_unit_evidence_no_dash():
    # no unit-like sibling AND no scalar default proof → nulls are left for the component's own null handling
    payload = {"railVM": {"aiSummaryText": None, "quickStatsLayout": "grid"}}
    default = {"railVM": {"aiSummaryText": "seed text", "quickStatsLayout": "grid"}}
    D.apply(payload, default)
    assert payload["railVM"]["aiSummaryText"] is None
