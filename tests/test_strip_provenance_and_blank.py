"""grounding.strip_to_placeholders — provenance-marker scrub (card 47) + honest-blank scalar option (card 11/74).
Pure unit tests (no DB dependency for the synthetic cases; the strip reads editable policy rows with code defaults)."""
from __future__ import annotations

from grounding.default_assemble import strip_to_placeholders


def test_provenance_marker_value_is_scrubbed():
    # a 'source':'mock' Storybook provenance marker must NOT survive into a live payload (card 47)
    out = strip_to_placeholders({"snapshot": {"source": "mock", "vThd": {"valuePct": 5.4, "unit": "%"}}})
    assert out["snapshot"]["source"] == ""                       # neutralised, never 'mock'


def test_provenance_scrub_is_value_typed_not_key_typed():
    # a legitimate label whose VALUE is not a provenance token is preserved; only exact token VALUES are scrubbed
    out = strip_to_placeholders({"label": "Sample Rate", "origin": "demo", "title": "Real Card"})
    assert out["label"] == "Sample Rate"                         # 'Sample Rate' is not a token → kept
    assert out["origin"] == ""                                   # 'demo' IS a token → scrubbed
    assert out["title"] == "Real Card"


def test_default_scalar_placeholder_is_zero_live_fill_path_unchanged():
    out = strip_to_placeholders({"stat": {"value": 420, "unit": "V"}})
    assert out["stat"]["value"] == 0.0                           # keeps the prop numeric for the live-fill path


def test_honest_blank_scalar_option_nulls_data_leaves():
    # the honest-blank caller passes scalar=None so a data-less card dashes to '—' instead of a fabricated 0.0
    out = strip_to_placeholders({"stat": {"value": 420, "unit": "V"}}, scalar=None)
    assert out["stat"]["value"] is None
    # chrome (unit/label) is preserved either way
    assert out["stat"]["unit"] == "V"


def test_series_of_objects_preserves_element_shape_under_null_strip():
    out = strip_to_placeholders({"actualLoad": [{"time": "00:00", "value": 68}]}, scalar=None)
    assert isinstance(out["actualLoad"], list) and isinstance(out["actualLoad"][0], dict)
    assert out["actualLoad"][0]["value"] is None                 # element value nulled, object shape kept


# ── ROLE-BASED string scrub (grounding.role_scrub, wired into strip_to_placeholders) ─────────────────
# These lock in the SLOT-ROLE rule: blank an ACTIVE / DERIVED-PICK / EVENT string assertion, KEEP a
# lookup-dictionary / enum / roster-identity chrome — distinguished by the PARENT-KEY ROLE, never the string.

def test_derived_pick_object_all_attrs_blanked():
    # (A) a worst*/selectedPanel object IS 'which panel scored worst' + its derived facts → blank every attr.
    out = strip_to_placeholders({"stats": {"worstCurrent": {
        "id": "ups-04", "panel": "UPS-04", "table": "MFM_033", "status": "warning", "causeKey": "normal"}}})
    w = out["stats"]["worstCurrent"]
    assert w == {"id": "", "panel": "", "table": "", "status": "", "causeKey": ""}


def test_roster_blanks_derived_facts_keeps_identity():
    # (B) a roster row: blank the derived verdict + DB pointer, KEEP the dropdown identity {id,panel}.
    out = strip_to_placeholders({"summary": {"period": {"panels": [
        {"id": "ups-01", "panel": "UPS-01", "table": "MFM_025", "status": "warning", "causeKey": "capacitorStep"}]}}})
    p = out["summary"]["period"]["panels"][0]
    assert p["id"] == "ups-01" and p["panel"] == "UPS-01"        # roster identity KEPT
    assert p["table"] == "" and p["status"] == "" and p["causeKey"] == ""   # derived facts BLANK


def test_active_status_object_blanked_but_vocab_dictionary_kept():
    # (C) status.label/statusKey (active verdict) BLANK; statusVocab / insightVocab dictionary KEEP byte-identical.
    out = strip_to_placeholders({"health": {"data": {
        "status": {"tone": "warning", "label": "Elevated", "statusKey": "elevated"},
        "insightKey": "currentElevated",
        "statusVocab": {"normal": "Normal", "elevated": "Elevated"},
        "insightVocab": {"currentBalanced": "Current loading is balanced."}}}})
    hd = out["health"]["data"]
    assert hd["status"] == {"tone": "", "label": "", "statusKey": ""}    # active verdict BLANK
    assert hd["insightKey"] == ""                                       # active pointer BLANK
    assert hd["statusVocab"] == {"normal": "Normal", "elevated": "Elevated"}   # dictionary KEEP (same 'Elevated' word)
    assert hd["insightVocab"] == {"currentBalanced": "Current loading is balanced."}


def test_event_instance_list_empties_to_zero_occurrences():
    # (D→d) an anomaly/event INSTANCE LIST strips to [] — a per-element blank still rendered N ghost event markers
    # 'as if real' (c67 5 skeleton events on a zero-event DG); the element COUNT is itself data. The honest rest state
    # of an occurrence list is EMPTY; the eventTypeKeys lookup dictionary stays byte-identical.
    out = strip_to_placeholders({"data": {"anomalies": [
        {"title": "Welding Overlap", "label": "Welding\nOverlap (+25%)", "type": "surge",
         "axis": "pct", "unit": "%", "series": "fuelLevel", "color": "#237492"}],
        "eventTypeKeys": {"sag": "Sag events", "swell": "Swell events"}}})
    assert out["data"]["anomalies"] == []                               # skeleton list → zero occurrences
    assert out["data"]["eventTypeKeys"] == {"sag": "Sag events", "swell": "Swell events"}   # dictionary KEEP


def test_band_dictionary_status_and_reference_tone_kept():
    # KEEP: a bandThresholds/statusLegend status is a band-NAME dictionary; a referenceLines tone is a fixed line style.
    out = strip_to_placeholders({
        "heatmap": {"bandThresholds": {"stops": {"kw": [{"status": "critical"}]}},
                    "statusLegend": [{"status": "low"}]},
        "trend": {"view": {"referenceLines": [{"tone": "reference"}],
                           "totals": [{"tone": "success"}]}}})
    assert out["heatmap"]["bandThresholds"]["stops"]["kw"][0]["status"] == "critical"   # band dict KEEP
    assert out["heatmap"]["statusLegend"][0]["status"] == "low"                         # legend dict KEEP
    assert out["trend"]["view"]["referenceLines"][0]["tone"] == "reference"             # static line style KEEP
    assert out["trend"]["view"]["totals"][0]["tone"] == ""                              # per-total live verdict BLANK


def test_fabricated_mfm_pointer_blanked_anywhere():
    # (F) any string whose VALUE is a fabricated MFM_xx pointer is blanked regardless of slot.
    out = strip_to_placeholders({"anySlot": {"tableRef": "MFM_034"}, "keep": {"label": "UPS-04"}})
    assert out["anySlot"]["tableRef"] == ""
    assert out["keep"]["label"] == "UPS-04"                       # a real roster-like label is not an MFM pointer → kept


def test_presentation_dictionary_container_spares_same_named_caption():
    # a static caption inside the presentation dictionary container is KEPT even though the same key name (severityLabel)
    # is a global active pointer elsewhere — distinguished by the dictionary-subtree ancestor, not the string.
    out = strip_to_placeholders({"snapshot": {
        "severityLabel": "High",                                  # ACTIVE verdict → BLANK
        "ieeeState": "fail",                                      # ACTIVE compliance result → BLANK
        "presentation": {"complianceStrip": {
            "severityLabel": "Severity", "complianceWords": {"fail": "Fail", "pass": "Pass"}}}}})
    assert out["snapshot"]["severityLabel"] == "" and out["snapshot"]["ieeeState"] == ""
    assert out["snapshot"]["presentation"]["complianceStrip"]["severityLabel"] == "Severity"   # static caption KEEP
    assert out["snapshot"]["presentation"]["complianceStrip"]["complianceWords"] == {"fail": "Fail", "pass": "Pass"}
