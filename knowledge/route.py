"""knowledge/route.py — ONE concern: classify a command-center prompt as dashboard | knowledge | off_domain.

The KNOWLEDGE pipeline is SEPARATE from the card pipeline (user directive 2026-07-06): conceptual electrical/
mechanical/energy questions ("what is voltage", "what are transformers") get a single restricted LLM answer; asset/
data prompts flow to the existing card pipeline UNCHANGED; everything else ("who is George Bush") is refused.

FAIL-OPEN: any transport/parse/config failure returns "dashboard" so the existing pipeline behavior is never blocked
by this pre-route. Valve: app_config `knowledge.enabled` ('on' unless 'off'). Prompt file: knowledge/prompts/router.md.
"""
import os

from llm.client import call_qwen

_KINDS = ("dashboard", "knowledge", "off_domain")
_SCHEMA = {
    "type": "object",
    "properties": {"kind": {"type": "string", "enum": list(_KINDS)}},
    "required": ["kind"],
    "additionalProperties": False,
}


def _prompt_text(name):
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts", name)
    with open(p, encoding="utf-8") as f:
        return f.read()


def enabled():
    try:
        from config.app_config import cfg
        return str(cfg("knowledge.enabled", "on")).strip().lower() != "off"
    except Exception:
        return True


def classify(prompt):
    """'dashboard' | 'knowledge' | 'off_domain' — dashboard on ANY failure (fail-open, never blocks the pipeline)."""
    if not enabled():
        return "dashboard"
    try:
        out = call_qwen(_prompt_text("router.md"), f"PROMPT: {prompt!r}",
                        stage="knowledge_route", schema=_SCHEMA) or {}
        kind = str(out.get("kind", "")).strip().lower()
        return kind if kind in _KINDS else "dashboard"
    except Exception:
        return "dashboard"
