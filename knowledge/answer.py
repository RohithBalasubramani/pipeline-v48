"""knowledge/answer.py — ONE concern: answer a conceptual EMS/electrical/mechanical question with the restricted
educator prompt (knowledge/prompts/system.md). No plant data, no fabrication — live values are the card pipeline's job.

Returns {"kind": "knowledge", "answer": str, "refused": bool}. The REFUSAL line for off-domain prompts is a
cmd_catalog-editable row (knowledge.refusal_line) mirroring the system prompt's hard restriction #1, so the router's
off_domain branch and the model's own refusal read identically."""
import os

from llm.client import call_qwen

_REFUSAL_DEFAULT = "I can only answer electrical, mechanical and energy-management questions for this EMS."
_SCHEMA = {
    "type": "object",
    "properties": {"answer": {"type": "string"}},
    "required": ["answer"],
    "additionalProperties": False,
}


def refusal_line():
    try:
        from config.app_config import cfg
        return str(cfg("knowledge.refusal_line", _REFUSAL_DEFAULT)) or _REFUSAL_DEFAULT
    except Exception:
        return _REFUSAL_DEFAULT


def _system():
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts", "system.md")
    with open(p, encoding="utf-8") as f:
        return f.read()


def refuse():
    return {"kind": "knowledge", "answer": refusal_line(), "refused": True}


def answer(prompt):
    """One restricted LLM call. An empty/failed answer degrades to the refusal line (honest — never a fabricated
    paragraph, never an unexplained blank)."""
    try:
        out = call_qwen(_system(), f"QUESTION: {prompt}", stage="knowledge_answer", schema=_SCHEMA) or {}
        text = str(out.get("answer", "")).strip()
    except Exception:
        text = ""
    if not text:
        return refuse()
    refused = text.strip() == refusal_line()
    return {"kind": "knowledge", "answer": text, "refused": refused}
