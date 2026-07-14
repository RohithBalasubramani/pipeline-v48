"""tests/test_resolver_section_ai.py — T0-9 [AI-first]: the resolver emits `section`, panel_sections VALIDATES it
against the pcc_panel_alias facts and falls back to the substring detector on a miss.

Off (default): schema has no `section` prop; the system prompt has no clause; stamping is detector-only
(byte-identical). On: the optional enum is added (required stays ['confident']); a fact-valid emission wins, an
invalid/absent one falls back to the detector, and the elided compare the detector misses is now caught."""
from unittest.mock import patch

import layer1b.resolve.answer_schema as SCH
import layer1b.resolve.panel_sections as PS


IDX = {"pcc1a": ("PCC-Panel-1", "A"), "pcc1b": ("PCC-Panel-1", "B"),
       "pcc2a": ("PCC-Panel-2", "A"), "pcc2b": ("PCC-Panel-2", "B")}


# ── schema gating ───────────────────────────────────────────────────────────────────────────────────────────────────

def test_schema_off_is_base_identity():
    # answer_schema imports flag_on lazily from config.app_config → patch it there
    with patch("config.app_config.flag_on", lambda k: k == "llm.guided_json.asset_resolve"):
        assert SCH.asset_answer_schema() is SCH.ASSET_ANSWER_SCHEMA   # section_ai off → identity preserved


def test_schema_none_when_guided_off():
    with patch("config.app_config.flag_on", lambda k: False):
        assert SCH.asset_answer_schema() is None


def test_schema_on_adds_optional_section_enum():
    with patch("config.app_config.flag_on", lambda k: True):
        sch = SCH.asset_answer_schema()
    assert sch is not SCH.ASSET_ANSWER_SCHEMA
    assert sch["properties"]["section"]["enum"] == ["A", "B", "both", "none"]
    assert sch["required"] == ["confident"]                        # NOT required (would bias the ambiguous shape)


# ── validation matrix (stamp_section_facts) ─────────────────────────────────────────────────────────────────────────

def _stamp(prompt, ai_section, panel="PCC-Panel-1"):
    asset = {"name": panel}
    with patch.object(PS, "pcc_section_index", lambda: dict(IDX)), \
         patch.object(PS, "member_scope", lambda p: "outgoing"):
        PS.stamp_section_facts(asset, prompt, ai_section=ai_section)
    return asset


def test_ai_single_section_validated():
    a = _stamp("voltage for the panel", "B")
    assert a.get("section") == "B" and "compare_sections" not in a


def test_ai_both_is_the_elided_compare_fix():
    # the prompt the substring detector MISSES ('comparepcc1aand1b' has pcc1a not pcc1b) — AI 'both' + fact-valid wins
    a = _stamp("compare pcc 1a and 1b", "both")
    assert a.get("compare_sections") == ["A", "B"] and "section" not in a


def test_ai_invalid_section_falls_back_to_detector():
    # panel has A/B, but the AI emits a section the panel doesn't have context for on a plain prompt → detector (None)
    a = _stamp("overview of the panel", "B", panel="PCC-Panel-2")
    # 'B' IS a real section of panel-2 per IDX → accepted; prove the fallback with a panel that has no sections:
    a2 = _stamp("overview", "A", panel="PCC-Panel-9")
    assert a2.get("section") is None and "compare_sections" not in a2   # 'A' not a real section of panel-9 → detector


def test_ai_none_lets_detector_decide():
    # explicit 'none' must NOT suppress a spelled alias the detector sees (detector wins on 'none')
    a = _stamp("voltage for pcc-1b", "none")
    assert a.get("section") == "B"


def test_ai_absent_is_detector_only():
    a = _stamp("compare pcc-1a and pcc-1b", None)                  # full spellings → detector catches the compare
    assert a.get("compare_sections") == ["A", "B"]
