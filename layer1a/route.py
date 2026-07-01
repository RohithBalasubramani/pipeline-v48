"""layer1a/route.py — the 1a storytelling-router LLM call: prompt -> page_key + metric + intent. [spec section 2 L1a, #19]

Routes ONLY among the pages enabled in config/available_pages.py (the add/remove provision).
"""
import os

from llm.client import call_qwen
from config.available_pages import filter_to_available
from layer1a.db_reads.page_specs import read_page_specs
from layer1a.db_reads.card_titles import read_card_titles
from layer1a.parse.page_key_fallback import resolve_page_key
from layer1a.parse.metric_intent_defaults import clamp_metric_intent

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load_prompt(name):
    with open(os.path.join(_HERE, "prompts", name)) as f:
        return f.read()


def _candidate_block(specs, titles):
    lines, shell = [], None
    for s in specs:
        if s["shell"] != shell:
            shell = s["shell"]
            lines.append(f"\n## SHELL: {shell or '(none)'}")
        blk = [f"- {s['page_key']}  | {s['title']}" + (f"  [{s['archetype']}]" if s["archetype"] else "")]
        if s["purpose"]:
            blk.append(f"    purpose: {s['purpose']}")
        if s["theme"]:
            blk.append(f"    theme: {s['theme']}")
        if s["answers"]:
            blk.append(f"    answers: {s['answers']}")
        blk.append(f"    cards: {titles.get(s['page_key'], '')[:160]}")
        lines.append("\n".join(blk))
    return "\n".join(lines)


def route(prompt, db="cmd_catalog", feedback=None):
    specs = filter_to_available(read_page_specs(db))   # <-- only available pages
    if not specs:
        raise RuntimeError("no available pages (config/available_pages.py) match the live DB")
    titles = read_card_titles(db)
    keys = [s["page_key"] for s in specs]
    system = _load_prompt("system.md")
    user = "PAGES:\n" + _candidate_block(specs, titles) + f"\n\nPROMPT: {prompt!r}\n"
    if feedback:                                        # reflect-loop: the prior template couldn't be answered → re-route
        user += ("\nRE-ROUTE FEEDBACK — the previously chosen template could NOT be answered by this asset's data. "
                 "Choose a DIFFERENT, answerable template:\n" + feedback + "\n")
    user += "JSON:"
    r = call_qwen(system, user)
    page_key = resolve_page_key(r.get("page_key"), keys)
    metric, intent = clamp_metric_intent(r.get("metric"), r.get("intent"))
    spec = next((s for s in specs if s["page_key"] == page_key), specs[0])
    return {"page_key": page_key, "metric": metric, "intent": intent, "page_spec": spec}
