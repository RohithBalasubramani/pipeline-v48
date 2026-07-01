"""layer1a/story_builder.py — per-card analytical_story (what each card tells wrt role/function + the prompt). AI. [spec section 2 L1a]"""
import os
import re

from llm.client import call_qwen
from layer1a.db_reads.cards_intent import read_page_cards

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load_prompt(name):
    with open(os.path.join(_HERE, "prompts", name)) as f:
        return f.read()


def _norm_id(k):
    """Tolerate keys like 'card 44', '44', 44 -> '44' (the model sometimes echoes the listing prefix)."""
    m = re.search(r"\d+", str(k))
    return m.group(0) if m else str(k)


def build_stories(prompt, page_key, metric, intent, db="cmd_catalog"):
    cards = read_page_cards(page_key, db)
    if not cards:
        return cards
    listing = "\n".join(
        f"- card {c['card_id']} | {c['title']} | role: {c['analytical_role']} | purpose: {c['card_purpose'][:80]}"
        for c in cards
    )
    system = _load_prompt("story_instruction.md")
    user = (f"PROMPT: {prompt!r}\nMETRIC: {metric}  INTENT: {intent}\nPAGE: {page_key}\n"
            f"CARDS:\n{listing}\nJSON:")
    r = call_qwen(system, user)
    stories = r.get("stories", {}) if isinstance(r, dict) else {}
    norm = {_norm_id(k): v for k, v in stories.items()}
    for c in cards:
        c["analytical_story"] = norm.get(str(c["card_id"]), "")
    return cards
