"""mutators/conversational.py — natural-speech wrappers from prompt_vocab (conv_prefix / conv_suffix): the same intent
phrased the way people actually type. Content untouched -> pin untouched (a wrapper-induced failure is a routing
defect). Skips a prefix whose first word the prompt already starts with ('show me show me...')."""
from __future__ import annotations

import random

NAME = "conversational"


def variants(text: str, ctx: dict, rng: random.Random) -> list[dict]:
    vocab = ctx.get("vocab") or {}
    prefixes = [r["value"] for r in vocab.get("conv_prefix", [])]
    suffixes = [r["value"] for r in vocab.get("conv_suffix", [])]
    out = []
    first_word = (text.split() or [""])[0].lower().strip(",")
    usable = [p for p in prefixes if p.split()[0].lower() != first_word]
    for p in rng.sample(usable, min(2, len(usable))):
        out.append({"name": "conversational:prefix", "text": f"{p} {text}", "weakens_pin": False})
    for s in rng.sample(suffixes, min(2, len(suffixes))):
        out.append({"name": "conversational:suffix", "text": f"{text} {s}", "weakens_pin": False})
    if usable and suffixes:
        p, s = rng.choice(usable), rng.choice(suffixes)
        out.append({"name": "conversational:wrap", "text": f"{p} {text} {s}", "weakens_pin": False})
    return out
