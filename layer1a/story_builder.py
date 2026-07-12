"""layer1a/story_builder.py — per-card analytical_story (what each card tells wrt role/function + the prompt). AI. [spec section 2 L1a]"""
import os
from llm.prompt_load import load as _prompt_load
import re

from llm.client import call_qwen
from layer1a.db_reads.cards_intent import read_page_cards

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load_prompt(name):
    return _prompt_load(_HERE, name)   # the ONE loader (llm/prompt_load, D8); errors="replace" house default


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
    # stage='stories' names this call site in llm/obs failure telemetry + keys the per-stage timeout row
    # (app_config llm.timeout.stories, base llm.timeout fallback). on_error='marker' distinguishes an OUTAGE from an
    # honest empty emission — before this, a transport failure set every story='' silently and that empty story rode
    # into every L2 emit unattributed (stage='-'). [AI_QUALITY_BACKLOG item 15]
    # DECISION INSPECTOR: generative annotation (no option set) — the card roster it writes stories for rides as context.
    from obs import llm_tap
    llm_tap.set_decision(kind="generative", subject="per-card analytical_story",
                         card_ids=[c["card_id"] for c in cards], page_key=page_key)
    r = call_qwen(system, user, stage="stories", on_error="marker")
    if isinstance(r, dict) and r.get("_llm_error"):
        try:  # telemetry only — the degrade path (every story '') is unchanged
            from obs import ai_log, failures
            failures.record("layer1a", "stories_llm_failed",
                            detail=f"{r['_llm_error']}: {r.get('_llm_error_detail', '')} — every story degrades to ''",
                            run_id=getattr(ai_log, "_RUN_ID", "default"))
        except Exception:
            pass
    stories = r.get("stories", {}) if isinstance(r, dict) else {}
    norm = {_norm_id(k): v for k, v in stories.items()}
    for c in cards:
        c["analytical_story"] = norm.get(str(c["card_id"]), "")
    return cards
