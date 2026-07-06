"""layer2/catalog/card_fill_recipe.py — the ATOMIZED per-card fill-recipe row (cmd_catalog.card_fill_recipe).
[generalization package §2c]

Single concern: read ONE card's {handling_class, roster_spec} — the executable member-scope recipe the Layer-2 user
message shows VERBATIM and gates.gate_roster validates the AI's data_instructions.roster against. Expands intra-row
{"$same_as_slot": "<slot>"} references (a row stays human-editable without triple-duplicating a shared element JSON)
before anything downstream sees the spec. No row → {} (honest-degrade: no roster context, no roster gate)."""
import json

from data.db_client import q


def _expand(spec):
    """Resolve {"$same_as_slot": "<slot>"} values against the row's OWN slots: the ref replaces itself with the
    referenced slot's SAME-NAMED key (e.g. consumers[].element ← sources[].element). Intra-row only, one level."""
    slots = (spec or {}).get("slots") or []
    by_slot = {s.get("slot"): s for s in slots if isinstance(s, dict)}
    for s in slots:
        if not isinstance(s, dict):
            continue
        for k, v in list(s.items()):
            if isinstance(v, dict) and "$same_as_slot" in v:
                src = by_slot.get(v["$same_as_slot"]) or {}
                s[k] = src.get(k)
    return spec


def read(card_id):
    """{handling_class, roster_spec} from cmd_catalog.card_fill_recipe; {} when the card has no recipe row."""
    r = q("cmd_catalog",
          f"SELECT handling_class, roster_spec::text FROM card_fill_recipe WHERE card_id={int(card_id)}")
    if not r or not r[0]:
        return {}
    try:
        spec = json.loads(r[0][1]) if r[0][1] else None
    except (ValueError, TypeError):
        spec = None
    return {"handling_class": r[0][0], "roster_spec": _expand(spec) if spec else None}
