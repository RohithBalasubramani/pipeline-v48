"""layer2/emit/emit.py — the ONE Layer-2 per-card AI call. Composes the 3 atomic prompt parts (swap + metadata +
data_instructions) into the system prompt, builds the user message, calls Qwen, returns the raw Layer2CardOutput. [PROMPTS §L2(a)(d)]"""
import os

from llm.client import call_qwen
from layer2.emit.user_message import build_user

_P = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompts")


def _system():
    parts = []
    for name in ("swap.md", "metadata.md", "data_instructions.md"):
        with open(os.path.join(_P, name)) as f:
            parts.append(f.read().strip())
    return "\n\n".join(parts)


def emit(card_in):
    return call_qwen(_system(), build_user(card_in), timeout=120) or {}
