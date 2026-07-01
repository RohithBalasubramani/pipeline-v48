"""layer1a/schema.py — assemble + validate the full (enriched) Layer1aOutput. [contract 2/4]"""

_INTENTS = {"trend", "distribution", "snapshot", "table", "events"}
_LAYOUT_KEYS = ("layout_primitive", "grid_template_columns", "grid_template_rows",
                "layout_gap", "layout_padding", "layout_shape", "render_shell")


def build_layer1a_output(route_result, cards, layout, groups):
    spec = route_result["page_spec"]
    return {
        "page_key": route_result["page_key"],
        "page_title": spec.get("title", ""),
        "shell": spec.get("shell", ""),
        "module": layout.get("module"),
        "metric": route_result["metric"],
        "intent": route_result["intent"],
        "story": spec.get("theme", "") or spec.get("answers", ""),
        "layout": {k: layout.get(k) for k in _LAYOUT_KEYS},
        "cards": [
            {"card_id": c["card_id"], "title": c["title"],
             "analytical_story": c.get("analytical_story", ""),
             "role_in_story": c.get("analytical_role", ""),
             "slot": c["slot"], "size": c["size"],
             "profile": c.get("profile", {}),    # what the card IS / answers (for swap reasoning)
             "recipe": c.get("recipe", {}),       # the DATA spec Layer 2 builds data_instructions from
             "handling": c.get("handling", {})}   # how it's produced/rendered (data_fill_shape signal)
            for c in cards
        ],
        "interdependency_groups": groups,
    }


def validate_layer1a_output(out, live_page_keys):
    """Plan-conformance check (contract 2, enriched). Returns list of problems (empty = OK)."""
    p = []
    if out.get("page_key") not in live_page_keys:
        p.append(f"page_key not available: {out.get('page_key')!r}")
    if not out.get("metric"):
        p.append("metric empty")
    if out.get("intent") not in _INTENTS:
        p.append(f"intent not in enum: {out.get('intent')!r}")
    if not isinstance(out.get("cards"), list) or not out["cards"]:
        p.append("cards missing/empty")
    for c in out.get("cards", []):
        if not isinstance(c.get("card_id"), int):
            p.append(f"card_id not int: {c.get('card_id')!r}")
        for k in ("slot", "size", "profile", "recipe", "handling"):
            if k not in c:
                p.append(f"card {c.get('card_id')} missing {k}")
    card_ids = {c["card_id"] for c in out.get("cards", [])}
    for g in out.get("interdependency_groups", []):
        if not set(g.get("card_ids", [])) <= card_ids:
            p.append(f"group {g.get('group_id')} references off-page cards")
    return p
