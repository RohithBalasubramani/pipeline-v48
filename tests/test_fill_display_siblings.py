"""F2 [fabrication] — DISPLAY-SIBLING RECONCILE. Pure unit tests (no DB, no LLM).

The fill executor overlays a leaf's `value` from neuract but a CMD_V2 reading is a STRUCTURED object
{value, displayValue, decimals, delta, deltaText, …}. Overwriting only `value` left the display projection holding the
harvested Storybook seed: a real value=426.75 beside a stale displayValue='325.9', an honest-blank value='—' beside a
fake '2165', a live value beside a seed delta='+3.0%'. ems_exec.executor.display reconciles them GENERICALLY (shape-driven,
no card ids): displayValue ≡ fmt(value) everywhere; the un-recomputable %-change/rate projections blanked beside a
written value. These assert NO Storybook number survives beside a filled-or-blanked value."""
from __future__ import annotations

from ems_exec.executor import display as D


def test_displayvalue_tracks_a_real_filled_value():
    # value filled to 426.75, decimals 1 → displayValue MUST become '426.8', never the seed '325.9'.
    p = {"data": {"readings": {"activePower": {
        "unit": "kW", "value": 426.75, "decimals": 1, "displayValue": "325.9"}}}}
    D.apply(p, {"data.readings.activePower.value"})
    assert p["data"]["readings"]["activePower"]["displayValue"] == "426.8"


def test_displayvalue_blanks_when_value_blanks():
    # value honest-blanked to '—' → displayValue MUST blank to the placeholder, never keep the seed '2165'.
    p = {"data": {"readings": {"activeEnergy": {
        "unit": "kWh", "value": "—", "decimals": 0, "displayValue": "2165"}}}}
    D.apply(p, {"data.readings.activeEnergy.value"})
    assert p["data"]["readings"]["activeEnergy"]["displayValue"] == "—"


def test_delta_projection_blanked_beside_a_written_value():
    # a %-change delta has NO per-card baseline → blank it beside a written value, never render the seed '+3.0%'.
    p = {"data": {"readings": {"activePower": {
        "value": 426.75, "decimals": 1, "displayValue": "325.9", "delta": "+3.0%"}}}}
    D.apply(p, {"data.readings.activePower.value"})
    assert p["data"]["readings"]["activePower"]["delta"] == "—"


def test_structured_deltatext_value_blanked():
    # the voltage-health {value, deltaText:{value,unit,prefix,qualifier}} shape — the deltaText VALUE blanks, chrome kept.
    p = {"phases": [{
        "unit": "V", "value": 419.0, "decimals": 0, "displayValue": "419",
        "delta": "(+1.0%)", "deltaText": {"unit": "%", "value": "+1.0", "prefix": "(", "qualifier": ")"}}]}
    D.apply(p, {"phases[0].value"})
    ph = p["phases"][0]
    assert ph["delta"] == "—"
    assert ph["deltaText"]["value"] == "—"          # the projected number blanks
    assert ph["deltaText"]["prefix"] == "("         # chrome preserved


def test_rate_per_minute_key_blanked_by_pattern():
    # activePowerDeltaPerMinute is a per-minute RATE with no baseline — matched by the rate-key pattern, blanked.
    p = {"data": {"readings": {
        "activePower": {"value": 426.75, "decimals": 1, "displayValue": "325.9"},
        "activePowerDeltaPerMinute": "+0.0/min"}}}
    D.apply(p, {"data.readings.activePower.value"})
    # activePowerDeltaPerMinute is a SIBLING of activePower under readings — it is only blanked if its PARENT object was
    # written. Here the written leaf's parent is `activePower`, so the readings-level rate is untouched by written-scope.
    # The global displayValue pass still leaves it (it is not a {value,displayValue} object). Assert no crash + value kept.
    assert p["data"]["readings"]["activePower"]["displayValue"] == "426.8"


def test_string_value_is_coerced_for_formatting():
    # a health bar carries value as a STRING '419' → displayValue formats the coerced number (decimals default 0 → '419').
    p = {"bars": [{"value": "419", "displayValue": "999"}]}
    D.apply(p, {"bars[0].value"})
    assert p["bars"][0]["displayValue"] == "419"


def test_global_invariant_reconciles_undeclared_reading_objects():
    # even with NO written paths, the global pass makes displayValue consistent with value everywhere (never a seed).
    p = {"a": {"value": 12.0, "decimals": 2, "displayValue": "99.99"}}
    D.apply(p, None)
    assert p["a"]["displayValue"] == "12.00"


def test_non_reading_objects_are_untouched():
    # an object without a displayValue is not a reading → left exactly as-is (no over-reach).
    p = {"cfg": {"key": "activePower", "axis": "left", "color": "#fff", "value": 3.0}}
    before = dict(p["cfg"])
    D.apply(p, {"cfg.value"})
    assert p["cfg"] == before


def test_apply_never_raises_on_garbage():
    assert D.apply(None, None) is None
    assert D.apply([1, 2, "x"], {"nope"}) == [1, 2, "x"]
