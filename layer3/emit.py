"""layer3/emit.py — the ONE L3 AI CALL (per card, parallel). The 3rd and last AI layer of the whole pipeline.

Composes the L3 system + user prompt (prompt.py) from the fact-sheet (factsheet.py) and calls Qwen once. Returns the
raw RenderSpec dict (names + booleans + reason ONLY). call_qwen fails open to {} — a {} here is treated by schema.py as
an emit failure and the card honest-degrades (never a fabricated render). No values, no fetches happen in this file.
[contract L3: "the ONE L3 AI call"]
"""
from llm.client import call_qwen
from layer3.prompt import SYSTEM, build_user


def emit_render_spec(factsheet, *, timeout=120):
    """The single L3 call. `factsheet` is the stripped names/flags sheet from layer3.factsheet.build_factsheet.
    Returns the raw RenderSpec dict (validated + persisted downstream by schema.py), or {} on a fail-open Qwen error."""
    return call_qwen(SYSTEM, build_user(factsheet), timeout=timeout) or {}
