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

_ON = ("1", "true", "yes", "t", "on")     # same truthy vocabulary as config/app_config.py _cast('bool')


def asset_answer_schema():
    """ASSET_ANSWER_SCHEMA when llm.guided_json.asset_resolve is on, else None (default: off / absent row / DB down —
    call_qwen then builds today's byte-identical json_object request). Never raises, never blocks import."""
    try:
        from config.app_config import cfg
        on = str(cfg("llm.guided_json.asset_resolve", "off")).strip().lower() in _ON
    except Exception:
        on = False
    return ASSET_ANSWER_SCHEMA if on else None
