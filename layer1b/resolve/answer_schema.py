"""layer1b/resolve/answer_schema.py — the asset resolver's guided-decoding answer schema. [item 17 stage 1]

Single concern: when the app_config flag row llm.guided_json.asset_resolve is 'on' (DEFAULT 'off' — seeded off by
db/seed_item17_guided_json.sql), hand llm/client.py the JSON schema of the resolver's answer so vLLM structured output
(response_format json_schema — probed live on :8200 vLLM 0.16.1rc1; the legacy `guided_json` extra-body param is
silently IGNORED by that server, a fenced non-schema reply came back) makes an unparseable emission impossible.
Flag off → None → call_qwen's json_schema kwarg is inert and the request is byte-identical to today's default path.

The schema mirrors the answer contract at the bottom of layer1b/prompts/asset_system.md and constrains ONLY as much
as that contract does — the prompt teaches THREE shapes:
    confident  {"names":["<exact>"],"confident":true}
    ambiguous  {"confident":false,"candidates":[...]}          <- NO names key in the taught shape
    empty      {"names":[],"confident":true}
so `candidates` is INCLUDED (the ambiguous branch answers through it — constraining it away would collapse the picker
list) and ONLY `confident` is required. Requiring `names` was PROVEN WRONG in the live 40-call control replay
(tools/replay_item17_guided_asset_resolve.py, 2026-07-06): the grammar forces the required first property, so an
ambiguous answer ('power quality for a spare feeder') got biased into the confident-pin shape and PINNED an arbitrary
spare — a decision flip the item-17 acceptance forbids. With required=["confident"] the grammar admits all three
taught shapes verbatim (property ORDER names→confident→candidates matches them; optional keys may be omitted), and
resolve_asset already treats an absent names/candidates as [] and an absent confident as False.
"""

ASSET_ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "names": {"type": "array", "items": {"type": "string"}},
        "confident": {"type": "boolean"},
        "candidates": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["confident"],
}

# T0-9 [resolver.section_ai]: an OPTIONAL bus-section emission the model may add — 'A'/'B' for a single-section view,
# 'both' for a section compare ('compare pcc 1a and 1b'), 'none' otherwise. Added to the properties ONLY when the flag
# is on; `required` stays ['confident'] (a REQUIRED key was PROVEN to bias the ambiguous shape — see the docstring), so
# every taught answer shape still validates. layer1b/resolve/panel_sections.stamp_section_facts VALIDATES the emission
# against the pcc_panel_alias facts and falls back to the substring detector on a miss (AI decides; deterministic
# validates + falls back). Property order after `candidates`, matching the emit contract.
_SECTION_PROP = {"section": {"type": "string", "enum": ["A", "B", "both", "none"]}}
# T1-10 [resolver.member_direction_ai]: an OPTIONAL panel reading-side emission — 'incomer' (supply/upstream) vs
# 'outgoing' (the fed feeders/bays, the default). Added to the properties ONLY when the flag is on; validated by the
# enum clamp + the keyword scan fallback in _finish (AI decides; deterministic validates + falls back).
_MEMBER_DIR_PROP = {"member_direction": {"type": "string", "enum": ["incomer", "outgoing"]}}


def asset_answer_schema():
    """ASSET_ANSWER_SCHEMA when llm.guided_json.asset_resolve is on, else None (default: off / absent row / DB down —
    call_qwen then builds today's byte-identical json_object request). When resolver.section_ai and/or
    resolver.member_direction_ai are ALSO on, the schema gains those optional enums (`required` stays ['confident']).
    Never raises, never blocks import. Identity of the base object is preserved when both extras are off (test_item17
    pins `is`)."""
    try:
        from config.app_config import flag_on
        on = flag_on("llm.guided_json.asset_resolve")   # THE boolean-knob vocabulary (D6)
    except Exception:
        on = False
    if not on:
        return None
    extra = {}
    try:
        from config.app_config import flag_on as _f
        if _f("resolver.section_ai"):
            extra.update(_SECTION_PROP)
        if _f("resolver.member_direction_ai"):
            extra.update(_MEMBER_DIR_PROP)
    except Exception:
        extra = {}
    if not extra:
        return ASSET_ANSWER_SCHEMA                       # identity preserved (both extras off)
    return {"type": "object",
            "properties": {**ASSET_ANSWER_SCHEMA["properties"], **extra},
            "required": ASSET_ANSWER_SCHEMA["required"]}
