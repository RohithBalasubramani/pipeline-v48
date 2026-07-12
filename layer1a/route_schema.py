"""layer1a/route_schema.py — the 1a PAGE-ROUTER's guided-decoding answer schema. [L1a routing-determinism, item 17 sibling]

Single concern: when the app_config flag row llm.guided_json.route is 'on' (DEFAULT 'off' — seeded off by
db/seed_route_guided_json.sql), hand llm/client.py the JSON schema of the router's answer so vLLM structured output
(response_format json_schema — the SAME seam proven to stabilize the 1b asset resolver on :8200 vLLM 0.16.1rc1; the
legacy `guided_json` extra-body param is silently IGNORED by that server) makes an off-enum page_key emission
IMPOSSIBLE. Flag off → None → call_qwen's json_schema kwarg is inert and the request is byte-identical to today's
default path (json_object). This mirrors layer1b/resolve/answer_schema.asset_answer_schema() exactly.

WHY THIS FIXES THE MISROUTE [L1a routing non-determinism]: temperature-0 + pinned seed keeps greedy decoding stable
in ISOLATION, but a NEAR-TIE route can still flip run-to-run UNDER SWEEP LOAD — concurrent batch composition changes
the floating-point reduction order, so the barely-winning page_key differs between runs (pg08 energy-power↔a DG page,
pg11 engine-cooling↔operations-runtime, pg15 thermal-life↔power-quality, the compare lane↔DG operations-runtime). A
drifted-token answer then lands in the FUZZY resolve_page_key recovery (segment/substring), whose winner depends on
which candidate barely matched. Constraining page_key to the EXACT candidate `keys` enum (this prompt's shell/class
candidates, AFTER the availability + renderability + reroute-exclusion filters route.py already applied) removes the
whole drift+recovery surface: the grammar can only emit a VERBATIM candidate key, so resolve_page_key always returns
how='verbatim' and the same prompt yields the same page EVERY run. metric/intent are enum-constrained the same way to
the DB-driven vocab the clamp already enforces (config/metrics.py + config/intents.py), so a drifted metric/intent
token can't slip past either — a strict superset of the constraint the router always intended.

The schema is BUILT PER CALL (the candidate `keys` are prompt-specific), unlike the asset resolver's static answer
schema — so this exposes route_answer_schema(keys, metric_vocab, intent_vocab) rather than a module constant. Property
ORDER page_key→metric→intent→window matches the taught JSON reply shape in layer1a/prompts/system.md, and all four are
REQUIRED (the router contract always returns them; the clamp defaults any that a legacy json_object reply omits, but
under guided decoding the grammar guarantees they are present, exactly as required). `window` is the ONLY optional-vocab
one — its enum is read from config/windows.TIME_WINDOWS (+ a "none" sentinel), not passed in, since it never varies per
prompt the way the page_key candidates do.
"""

def route_answer_schema(keys, metric_vocab, intent_vocab):
    """The router's enum-constrained answer schema when llm.guided_json.route is on, else None (default: off / absent
    row / DB down → call_qwen builds today's byte-identical json_object request). Never raises, never blocks import.

    keys         — THIS prompt's candidate page_keys (route.py's `keys`, already availability/renderability/exclusion
                   filtered). page_key is enum-pinned to exactly these, so an off-list emission is impossible.
    metric_vocab — config/metrics.METRIC_VOCAB (the same list clamp_metric_intent enforces).
    intent_vocab — config/intents vocab (the same list the clamp enforces).

    WINDOW [prompt→date_window extraction, route-1a-timewindow]: a 4th enum property carrying the relative time range
    the prompt names ('last 7 days' → 'last-7-days'), pinned to the SAME DB-driven preset vocab config/windows.TIME_WINDOWS
    uses (IMPORTED here, never hardcoded — the schema can never drift from the clamp/executor vocabulary) PLUS a "none"
    sentinel for "no time mentioned". It is a PURE STRING enum (xgrammar treats it exactly like metric/intent) and
    REQUIRED like the others (the grammar always emits one under guided decoding; the clamp folds none/absent/invalid →
    None so the host keeps its today/latest default). Kept LAST to match the taught reply shape in prompts/system.md.
    """
    try:
        from config.app_config import flag_on
        on = flag_on("llm.guided_json.route")   # THE boolean-knob vocabulary (D6)
    except Exception:
        on = False
    if not on:
        return None
    try:
        from config.windows import TIME_WINDOWS
        window_enum = list((TIME_WINDOWS or {}).keys()) + ["none"]   # DB-driven presets + the no-time sentinel
    except Exception:
        window_enum = ["none"]
    return {
        "type": "object",
        "properties": {
            "page_key": {"type": "string", "enum": list(keys)},
            "metric": {"type": "string", "enum": list(metric_vocab)},
            "intent": {"type": "string", "enum": list(intent_vocab)},
            "window": {"type": "string", "enum": window_enum},
        },
        "required": ["page_key", "metric", "intent", "window"],
    }
