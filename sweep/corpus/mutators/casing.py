"""mutators/casing.py — capitalization variants over the WHOLE prompt (resolution is case-insensitive by contract:
layer1b _norm parity — so these never weaken the pin; a casing-induced picker IS a defect worth catching)."""
from __future__ import annotations

import random

NAME = "casing"


def variants(text: str, ctx: dict, rng: random.Random) -> list[dict]:
    ragged = "".join(ch.upper() if rng.random() < 0.5 else ch.lower() for ch in text)
    out = []
    for name, t in (("lowercase", text.lower()), ("uppercase", text.upper()),
                    ("titlecase", text.title()), ("raggedcase", ragged)):
        if t != text:
            out.append({"name": f"casing:{name}", "text": t, "weakens_pin": False})
    return out
