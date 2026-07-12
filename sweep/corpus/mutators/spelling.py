"""mutators/spelling.py — realistic typo families (drop / adjacent-swap / double-strike) aimed at the ASSET NAME
substring when the prompt carries one (a targeted resolution probe), else at the longest word (a routing probe).
Typos mangle the name -> weakens_pin (honest picker acceptable)."""
from __future__ import annotations

import random

NAME = "spelling"


def _typo_targets(text: str, ctx: dict) -> tuple[str, bool]:
    """(substring to typo, is_asset_name) — the asset name when present in the text, else the longest word."""
    for key in ("asset", "panel"):
        sub = ctx.get(key)
        if sub and sub in text:
            return sub, True
        if sub and sub.lower() in text:                    # a casing/template variant may carry it lowercased
            return sub.lower(), True
    words = sorted((w for w in text.split() if len(w) >= 5), key=len, reverse=True)
    return (words[0], False) if words else ("", False)


def variants(text: str, ctx: dict, rng: random.Random) -> list[dict]:
    target, is_name = _typo_targets(text, ctx)
    letters = [i for i, ch in enumerate(target) if ch.isalpha()]
    if len(letters) < 4:
        return []
    out = []
    i = rng.choice(letters[1:-1])
    out.append(("typo_drop", target[:i] + target[i + 1:]))
    j = rng.choice(letters[1:-1])
    if j + 1 < len(target):
        out.append(("typo_swap", target[:j] + target[j + 1] + target[j] + target[j + 2:]))
    k = rng.choice(letters)
    out.append(("typo_double", target[:k] + target[k] + target[k:]))
    return [{"name": f"spelling:{n}", "text": text.replace(target, t, 1), "weakens_pin": is_name}
            for n, t in out if t != target]
