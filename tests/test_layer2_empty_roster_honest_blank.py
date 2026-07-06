"""★ empty-roster honest-blank — the panel_aggregate payload_error root-cause fix (final sweep / page 05 card 21).

A panel_aggregate member card (e.g. card 21 'Current Distribution', a RadarPayload whose spokes are the panel's
feeders) that has NO card_fill_recipe roster_spec fills its per-member DATA from its backend_strategy consumer's panel
fan-out — NOT from fields[] and NOT from a roster. Two ways the AI's emit used to become a card-BLOCKING payload_error:

  (A) it emits fields:[] (data rides the member-aggregation consumer) → gate_data_instructions with fields_optional=
      False recorded 'data_instructions.fields is empty' → conforms=False → payload_error banner.
  (B) it ALSO emits a data_instructions.roster on a card with no roster_spec → gate_roster drops it to [] AND its
      'roster emitted for a card with no roster recipe' telemetry leaked into failure.detail → payload_error text.

THE MANDATE: degrade PER-LEAF, never per-card. Both must become an HONEST-BLANK render (the component mounts, its
member leaves blank with a reason), NOT a render-blocking payload_error. The fix is GENERIC — panel_aggregate is now a
DB-driven fields_optional class (gates.fields_optional_classes), and build.py drops the recipe-less-roster telemetry
out of the card-blocking failures (keeping it as a data_note). Zero card ids / vocab / shapes hardcoded.

Non-live: pure in-memory emit via monkeypatch (no LLM, no :5433). Reads only the cmd_catalog structure card 21 needs.
"""
import pytest

from layer2.gates import gate_data_instructions
from config.app_config import cfg


# ── unit-level: an empty-fields, empty-roster data_instructions for a fields-optional class CONFORMS (no payload_error)
def test_panel_aggregate_is_fields_optional():
    """panel_aggregate is in the DB-driven fields_optional set — its data rides the member-aggregation consumer.
    Read through the ONE shared accessor (config.gates_vocab [A6a]) so this asserts what prompt+gates actually use."""
    from config.gates_vocab import fields_optional_classes, FIELDS_OPTIONAL_DEFAULT
    optional = fields_optional_classes()
    assert "panel_aggregate" in optional, "panel_aggregate must be fields-optional (member-aggregation consumer fills it)"
    assert "panel_aggregate" in FIELDS_OPTIONAL_DEFAULT           # DB-outage parity: the code default carries all 5


def test_empty_fields_conforms_when_fields_optional():
    """fields:[] + no roster + fields_optional=True → the data gate is CLEAN (no 'fields is empty' payload_error)."""
    di = {"payload_shape": "RadarPayload", "fields": []}
    ok, issues = gate_data_instructions(di, {"columns": []}, fields_optional=True)
    assert ok, f"a member-aggregation card's empty fields must pass when fields-optional: {issues}"
    assert not any("fields is empty" in i for i in issues)


def test_empty_fields_still_fails_when_fields_required():
    """A genuinely fields-REQUIRED card (fields_optional=False) with empty fields + no roster still fails honestly."""
    di = {"payload_shape": "RadarPayload", "fields": []}
    ok, issues = gate_data_instructions(di, {"columns": [{"column": "voltage_avg"}]}, fields_optional=False)
    assert not ok and any("fields is empty" in i for i in issues)


# ── build-level: the full run_card path for card 21 with a synthetic empty-roster emit → honest-blank, not payload_error
def _l1a():
    return {"page_key": "panel-overview-shell/voltage-current", "metric": "current", "intent": "snapshot",
            "story": "Voltage & Current — PCC Panel 4", "interdependency_groups": [],
            "cards": [{"card_id": 21, "title": "Current Distribution at {period}",
                       "analytical_story": "per-feeder current distribution across the panel"}]}


def _l1b():
    # PCC Panel 4 (mfm 320): a PANEL asset whose own device table is empty — its data is the member fan-out.
    return {"asset": {"mfm_id": 320, "name": "PCC-Panel-4", "table": "pcc_panel_4_feedbacks",
                      "class": "Panel", "has_data": True, "has_feeders": True},
            "column_basket": {"tables": ["pcc_panel_4_feedbacks"], "columns": []}}


def _run_card21(monkeypatch, di, *, strip_roster_spec=False):
    import layer2.build as B
    import layer2.card_input as CI

    def fake_emit(ci):
        # a real harvested default_payload rides ci["catalog_row"]["default_payload"]; the producer authors
        # exact_metadata from it, so the metadata gate is satisfied and we isolate the DATA/roster path.
        return {"swap_decision": {"action": "keep"}, "exact_metadata": {}, "answerability": "full",
                "data_instructions": dict(di)}

    monkeypatch.setattr(B, "emit", fake_emit)
    # RECIPE-LESS scenario (B): card 21 is now a fully-provisioned roster card in cmd_catalog (it has a real
    # roster_spec). To exercise the recipe-LESS honest-blank path this test is about — "the AI emits a roster on a card
    # with NO roster recipe" — strip the roster_spec from the loaded catalog_row so the card genuinely has none. The
    # honest-blank normalization (gate_roster drops the stray roster to [], build.py keeps it a data_note not a
    # payload_error) is what we assert; keeping this deterministic vs the card's evolving DB recipe.
    if strip_roster_spec:
        _load = CI.load_catalog_row

        def _load_no_roster(card_id, page_key, title=None):
            cr = _load(card_id, page_key, title=title)
            rec = dict(cr.get("recipe") or {})
            rec.pop("roster_spec", None)
            cr = {**cr, "recipe": rec}
            return cr

        monkeypatch.setattr(CI, "load_catalog_row", _load_no_roster)
    return B.run_card("t21", 21, _l1a(), _l1b())


def test_card21_empty_fields_is_honest_blank(monkeypatch):
    """(A) card 21 emits fields:[] (data rides its consumer) → conforms=True, NO payload_error; the component renders."""
    out = _run_card21(monkeypatch, {"payload_shape": "RadarPayload", "fields": []})
    assert out["conforms"] is True, out.get("failure")
    assert out["failure"] is None, "empty fields on a member-aggregation card must NOT be a card-blocking failure"


def test_card21_emitted_roster_no_recipe_is_honest_blank(monkeypatch):
    """(B) card 21 ALSO emits a roster although it has NO roster_spec → dropped to [] AND its 'no roster recipe'
    telemetry stays a data_note, never a card-blocking payload_error. Component renders, members honest-blank."""
    di = {"payload_shape": "RadarPayload", "fields": [],
          "roster": [{"slot": "radar.spokes[]", "scope": "members",
                      "element": {"value": {"b": "col", "c": "current_avg"}}}]}
    out = _run_card21(monkeypatch, di, strip_roster_spec=True)
    assert out["conforms"] is True, out.get("failure")
    assert out["failure"] is None, "a recipe-less roster is honest-blank telemetry, not a payload_error"
    # the roster was normalized away (the consumer fans out members) — no stray recipe-less roster ships
    assert (out["data_instructions"].get("roster") or []) == []
    # the honest-blank reason is surfaced as telemetry (a user-facing note), not a blocking failure
    assert out["data_note"] and "honest-blank" in out["data_note"]
    assert out["answerability"] == "partial"            # per-leaf degrade, still renders — never a gap/re-route
    assert out["gap"] is False


def test_card21_renders_its_real_component(monkeypatch):
    """The card ALWAYS mounts its real component: a non-empty exact_metadata (RadarPayload frame) is produced."""
    out = _run_card21(monkeypatch, {"payload_shape": "RadarPayload", "fields": []})
    assert out["exact_metadata"], "the component must mount — a real metadata frame is authored from the default"
    # ZERO seed survives: the DATA leaves are elided (typed placeholders), never a copied Storybook demo number
    assert out["_default_payload"] is not None           # the raw default rides along for the offline seed check
