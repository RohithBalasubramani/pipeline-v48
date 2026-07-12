"""mutators/plural.py — plural/singular swaps on class + metric NOUNS (never the asset's unit token), from
prompt_vocab kind='plural' rows (value=plural, meta=singular), both directions. Word-level -> pin untouched."""
from __future__ import annotations

import random
import re

NAME = "plural"


def variants(text: str, ctx: dict, rng: random.Random) -> list[dict]:
    out = []
    for row in (ctx.get("vocab") or {}).get("plural", []):
        plural, singular = row["value"], row["meta"]
        if not singular:
            continue
        for src, dst, tag in ((singular, plural, "pluralize"), (plural, singular, "singularize")):
            pat = re.compile(rf"\b{re.escape(src)}\b", re.IGNORECASE)
            if pat.search(text):
                out.append({"name": f"plural:{tag}:{src}", "text": pat.sub(dst, text, count=1),
                            "weakens_pin": False})
    return out
