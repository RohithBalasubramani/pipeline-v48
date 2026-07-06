"""knowledge/ems.py — the ONE knowledge AI layer: ROUTE + ANSWER + REJECT in a SINGLE LLM call.

User directive (2026-07-06): routing, answering, and off-scope rejection are one AI layer. A prompt goes in; a
{kind, answer} comes back in ONE call:
  · kind='dashboard'  → answer='' → the host falls through to the card pipeline UNCHANGED (this layer defers).
  · kind='knowledge'  → answer = the educational electrical/mechanical/energy answer, written in this same call.
  · kind='off_scope'  → answer = the refusal line (people/politics/trivia/etc.).

Prompt: knowledge/prompts/ems.md. Valve: app_config `knowledge.enabled` ('on' unless 'off'). FAIL-OPEN: any
transport/parse/config failure returns kind='dashboard' with no answer, so the existing pipeline is NEVER blocked.
"""
import os

from llm.client import call_qwen

_KINDS = ("dashboard", "knowledge", "off_scope")
_REFUSAL_DEFAULT = "I can only answer electrical, mechanical and energy-management questions for this EMS."
_SCHEMA = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": list(_KINDS)},
        "answer": {"type": "string"},
    },
    "required": ["kind", "answer"],
    "additionalProperties": False,
}


def enabled():
    try:
        from config.app_config import cfg
        return str(cfg("knowledge.enabled", "on")).strip().lower() != "off"
    except Exception:
        return True


def refusal_line():
    try:
        from config.app_config import cfg
        return str(cfg("knowledge.refusal_line", _REFUSAL_DEFAULT)) or _REFUSAL_DEFAULT
    except Exception:
        return _REFUSAL_DEFAULT


def _prompt():
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts", "ems.md")
    with open(p, encoding="utf-8") as f:
        return f.read()


def _user_message(prompt, history):
    """Fold the prior knowledge turns in front of the new prompt so a FOLLOW-UP ("how is it measured", "give an
    example", "and for a transformer?") resolves its pronouns/ellipsis against the conversation. history = the earlier
    turns oldest-first [{prompt, answer}, ...]; empty/None → just the prompt (identical to the no-context path)."""
    turns = [t for t in (history or []) if isinstance(t, dict) and str(t.get("prompt", "")).strip()]
    if not turns:
        return f"PROMPT: {prompt}"
    lines = ["PRIOR CONVERSATION (resolve any follow-up/pronoun in the new prompt against this):"]
    for t in turns:
        lines.append(f"User: {str(t.get('prompt', '')).strip()}")
        a = str(t.get("answer", "")).strip()
        if a:
            lines.append(f"Assistant: {a}")
    lines += ["", f"PROMPT: {prompt}"]
    return "\n".join(lines)


def ask(prompt, history=None):
    """ONE call → {'kind','answer','refused'}. dashboard on ANY failure (fail-open; the card pipeline runs as before).
    An empty knowledge answer degrades to the refusal (honest — never a fabricated paragraph, never a blank).
    `history` = prior knowledge turns (oldest-first) so a follow-up question keeps the conversation's context."""
    if not enabled():
        return {"kind": "dashboard", "answer": "", "refused": False}
    try:
        out = call_qwen(_prompt(), _user_message(prompt, history), stage="knowledge_ems", schema=_SCHEMA) or {}
        kind = str(out.get("kind", "")).strip().lower()
        answer = str(out.get("answer", "")).strip()
    except Exception:
        kind, answer = "dashboard", ""
    if kind not in _KINDS:
        kind = "dashboard"
    if kind == "off_scope":
        return {"kind": "off_scope", "answer": refusal_line(), "refused": True}
    if kind == "knowledge":
        return {"kind": "knowledge", "answer": answer or refusal_line(), "refused": not answer}
    return {"kind": "dashboard", "answer": "", "refused": False}
