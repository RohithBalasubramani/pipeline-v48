"""tests/test_resolver_member_direction_ai.py — T1-10 [AI-first]: the resolver emits member_direction; the enum
clamp validates it and the keyword scan (member_scope) stays as the validator/fallback.

Off (default): schema has no member_direction prop; stamping is keyword-scan-only (byte-identical). On: the optional
enum is added (required stays ['confident']); a valid emission wins over the keyword scan, an invalid/absent one
falls back to the scan; ONE stamped member_scope value keeps dual-consumer parity."""
from unittest.mock import patch

import layer1b.resolve.answer_schema as SCH
import layer1b.resolve.panel_sections as PS


# ── schema gating ───────────────────────────────────────────────────────────────────────────────────────────────────

def test_schema_off_is_base_identity():
    with patch("config.app_config.flag_on", lambda k: k == "llm.guided_json.asset_resolve"):
        assert SCH.asset_answer_schema() is SCH.ASSET_ANSWER_SCHEMA


def test_schema_on_adds_member_direction_enum():
    with patch("config.app_config.flag_on",
               lambda k: k in ("llm.guided_json.asset_resolve", "resolver.member_direction_ai")):
        sch = SCH.asset_answer_schema()
    assert sch["properties"]["member_direction"]["enum"] == ["incomer", "outgoing"]
    assert sch["required"] == ["confident"] and "section" not in sch["properties"]


def test_schema_both_extras_compose():
    with patch("config.app_config.flag_on", lambda k: True):
        sch = SCH.asset_answer_schema()
    assert "section" in sch["properties"] and "member_direction" in sch["properties"]


# ── stamping (member_scope) ─────────────────────────────────────────────────────────────────────────────────────────

def _stamp(prompt, ai_dir):
    asset = {"name": "PCC-Panel-1"}
    with patch.object(PS, "pcc_section_index", lambda: {}), \
         patch.object(PS, "member_scope", lambda p: "outgoing"):     # keyword scan says outgoing
        PS.stamp_section_facts(asset, prompt, ai_member_direction=ai_dir)
    return asset


def test_ai_incomer_wins_over_keyword():
    a = _stamp("what feeds pcc-1", "incomer")                        # keyword scan misses this phrasing → outgoing
    assert a["member_scope"] == "incomer"


def test_ai_absent_falls_back_to_keyword():
    a = _stamp("outgoing feeders on pcc-1", None)
    assert a["member_scope"] == "outgoing"


def test_ai_invalid_falls_back_to_keyword():
    a = _stamp("pcc-1", "sideways")                                  # not in the enum → keyword scan
    assert a["member_scope"] == "outgoing"


def test_disagreement_is_recorded():
    rec = []
    with patch.object(PS, "pcc_section_index", lambda: {}), \
         patch.object(PS, "member_scope", lambda p: "outgoing"), \
         patch("obs.failures.record", lambda *a, **k: rec.append((a, k))):
        PS.stamp_section_facts({"name": "PCC-Panel-1"}, "supply side", ai_member_direction="incomer")
    assert any("member_direction_disagree" in str(c) for c in rec)
