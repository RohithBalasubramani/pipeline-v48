"""tests/test_residual_seed_strip.py — the LAST seed-leak classes (fullsweep_20260706_004334 closeout), PURE unit
tests (no DB required — every vocab/policy has a code-default mirror of db/seed_residual_seed_scrub.sql).

Locks in the four residual classes the build-time strip previously leaked:
  (a) OCCURRENCE BOOLEAN ARRAYS   — c55 activity.ticks [..true..true..] rendered 2 FAKE transfer events.
  (b) STRING-EMBEDDED MEASUREMENTS — c56/59 'Readiness: 70%', c17 'at 17', c71 'peak 77%', c51 'peak temp 35°C',
                                     c37/38 'Max - 420V', c48 'Max: 480V'.
  (c) SEEDED NUMERIC-STRING AXES  — c36 yLabels ['380'..'80'], c37/38 yTicks ['430'..'390'] shown as a live scale.
  (d) SEED EVENT SKELETONS        — c67 data.events ghost rows (covered in test_strip_provenance_and_blank too).
Plus: pure chrome captions stay, dictionaries stay, and the strip is IDEMPOTENT (strip(strip(x)) == strip(x))."""
from __future__ import annotations

from grounding.default_assemble import strip_to_placeholders, blank_data_leaves
from validate.leaf_classify import classify


# ── (a) occurrence boolean arrays ──────────────────────────────────────────────────────────────────
def test_occurrence_bool_ticks_classified_data_and_stripped_empty():
    # c55: a 30-slot transfer-activity tick rail with 2 seeded `true` events — the trues ARE data assertions.
    p = {"activity": {"ticks": [False] * 7 + [True] + [False] * 16 + [True] + [False] * 5,
                      "countLabel": "transfers", "tickStartLabel": "-30d", "tickEndLabel": "now"}}
    paths = {d["path"] for d in classify(p)["data_leaves"]}
    assert "activity.ticks" in paths                             # bool array under an activity/tick role = DATA
    out = strip_to_placeholders(p)
    assert out["activity"]["ticks"] == []                        # zero occurrences at rest — never a fake transfer
    assert out["activity"]["countLabel"] == "transfers"          # chrome kept
    assert out["activity"]["tickStartLabel"] == "-30d"           # relative-window chrome kept (no unit token)


def test_bool_array_outside_occurrence_role_stays_chrome():
    # a structural toggle list is NOT occurrence data — the role vocabulary gates the rule.
    p = {"layout": {"columnsVisible": [True, False, True]}}
    assert classify(p)["data_leaves"] == []
    assert strip_to_placeholders(p) == p


def test_graft_blank_also_empties_occurrence_bools():
    # blank_data_leaves shares leaf_classify — a grafted raw container cannot re-import the fake-transfer ticks.
    out = blank_data_leaves({"activity": {"ticks": [True, False, True], "countLabel": "transfers"}})
    assert out["activity"]["ticks"] == []
    assert out["activity"]["countLabel"] == "transfers"


# ── (b) string-embedded measurements in data-role slots ────────────────────────────────────────────
def test_embedded_measurement_annotations_scrubbed():
    out = strip_to_placeholders({
        "composite": {"floor": {"label": "Readiness: 70%", "value": 68.0}},                 # c56/59
        "duty": {"topKpis": [{"label": "Average Load", "value": 62.0, "sub": "peak 77%"}]},  # c71
        "demand": {"view": {"stats": [{"label": "Worst Peak", "value": "332", "unit": "kW",
                                       "sub": "at 17"}]}},                                   # c17
        "batteryHistory": {"peak": {"index": 30, "label": "peak temp 35°C", "color": "#c13b38"}},   # c51
        "data": {"thresholds": [{"label": "Max - 420V", "value": 420.0}],                    # c37/38
                 "maxLine": {"label": "Max: 480V", "value": 480.0}}})                        # c48
    assert out["composite"]["floor"] == {"label": "", "value": 0.0}
    assert out["duty"]["topKpis"][0]["sub"] == ""
    assert out["demand"]["view"]["stats"][0]["sub"] == ""
    assert out["demand"]["view"]["stats"][0]["value"] == 0.0            # KPI numeric-string already data
    assert out["batteryHistory"]["peak"]["label"] == ""
    assert out["batteryHistory"]["peak"]["color"] == "#c13b38"          # chrome kept
    assert out["data"]["thresholds"][0]["label"] == ""
    assert out["data"]["maxLine"]["label"] == ""


def test_pure_chrome_captions_without_measurement_stay():
    out = strip_to_placeholders({
        "series": [{"label": "5th Harmonic", "value": 6.2, "color": "#6488a3"}],   # ordinal ≠ measurement
        "view": {"rangeOptions": [{"label": "Last 7 days", "value": "last-7-days"}],  # no numeric sibling
                 "stats": [{"label": "IEEE 519 TDD", "value": 4.1}]},               # standard name ≠ measurement
        "legendItems": [{"label": "B-Phase", "value": 231.0, "color": "#237492"}]})
    assert out["series"][0]["label"] == "5th Harmonic"
    assert out["series"][0]["value"] == 0.0                              # the measured sibling still strips
    assert out["view"]["rangeOptions"][0]["label"] == "Last 7 days"
    assert out["view"]["stats"][0]["label"] == "IEEE 519 TDD"
    assert out["legendItems"][0]["label"] == "B-Phase"


def test_dictionary_and_design_chrome_subtrees_keep_embedded_numbers():
    # a REAL design band (bandThresholds) / lookup dictionary keeps its numbers and number-bearing labels.
    p = {"heatmap": {"bandThresholds": {"stops": {"kw": [{"label": "over 400V", "value": 400}]}}},
         "statusVocab": {"high": "above 90%"}}
    out = strip_to_placeholders(p)
    assert out == p


# ── (c) seeded numeric-string axes ─────────────────────────────────────────────────────────────────
def test_numeric_string_axis_arrays_classified_data_and_stripped():
    # c36/37/38: yTicks/yLabels of numeric STRINGS are the seed data's own scale — live-looking values, not chrome.
    p = {"data": {"yTicks": ["430", "422", "414", "406", "398", "390"],
                  "yLabels": ["380", "340", "300"],
                  "xAxisLabel": "Time"}}
    kinds = {d["path"]: d["kind"] for d in classify(p)["data_leaves"]}
    assert "data.yTicks" in kinds and "data.yLabels" in kinds
    out = strip_to_placeholders(p)
    assert out["data"]["yTicks"] == [] and out["data"]["yLabels"] == []
    assert out["data"]["xAxisLabel"] == "Time"                           # axis caption chrome kept


def test_numeric_string_list_outside_axis_role_stays_chrome():
    # an option/enum list of numeric-string VALUES is not an axis — the role key gates the rule.
    p = {"view": {"zoomLevels": ["1", "2", "4"]}}
    assert classify(p)["data_leaves"] == []
    assert strip_to_placeholders(p) == p


# ── (d) seed event skeletons ───────────────────────────────────────────────────────────────────────
def test_event_skeleton_lists_empty_but_event_object_and_dictionaries_stay():
    p = {"data": {"events": [{"color": "#f27e80", "index": 7, "seriesLabel": "R phase"}] * 5,
                  "eventTypeKeys": {"sag": "Sag events", "swell": "Swell events"},
                  "event": {"title": "Voltage Sag", "unit": "%"}}}
    out = strip_to_placeholders(p)
    assert out["data"]["events"] == []                                   # 5 ghost markers → zero occurrences
    assert out["data"]["eventTypeKeys"] == {"sag": "Sag events", "swell": "Swell events"}
    assert out["data"]["event"]["title"] == ""                           # singular event OBJECT: assertion blanked
    assert out["data"]["event"]["unit"] == "%"                           # …but its chrome shape stays (graftable)


# ── idempotence ────────────────────────────────────────────────────────────────────────────────────
def test_strip_is_idempotent_over_all_residual_classes():
    p = {"activity": {"ticks": [True, False], "count30d": 4},
         "composite": {"floor": {"label": "Readiness: 70%", "value": 68.0}},
         "data": {"yTicks": ["430", "390"], "events": [{"index": 7}],
                  "thresholds": [{"label": "Max - 420V", "value": 420.0}]},
         "statusVocab": {"high": "above 90%"}}
    once = strip_to_placeholders(p)
    assert strip_to_placeholders(once) == once                           # fixed point — 2nd build byte-identical
