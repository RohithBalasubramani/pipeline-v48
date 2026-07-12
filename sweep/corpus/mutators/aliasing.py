"""mutators/aliasing.py — name-form variants: (a) swap the typed panel name for a SIBLING ALIAS of the same panel
(ctx['aliases'], from pcc_panel_alias — aliases MUST resolve, pin NOT weakened: an alias-induced picker is a defect);
(b) reformat the unit token ('DG-1' -> 'dg 1' / 'dg01' / 'DG #1') — spacing/punctuation tolerance probes, weakened."""
from __future__ import annotations

import random
import re

NAME = "aliasing"

_UNIT = re.compile(r"([A-Za-z]{2,12})[\s\-_]*0?(\d{1,2})([ab]?)\b")


def variants(text: str, ctx: dict, rng: random.Random) -> list[dict]:
    out = []
    typed = next((ctx[k] for k in ("panel", "asset") if ctx.get(k) and ctx[k] in text), None)

    for alias in (ctx.get("aliases") or [])[:3]:
        if typed and alias and alias != typed:
            out.append({"name": "aliasing:sibling_alias", "text": text.replace(typed, alias, 1),
                        "weakens_pin": False})

    ms = list(_UNIT.finditer(typed or ""))
    m = ms[-1] if ms else None                             # the LAST unit token ('...-UPS-08'), never the site prefix
    if m and typed:
        head, num, ab = m.group(1), m.group(2), m.group(3)
        for tag, form in (("token_space", f"{head.lower()} {num}{ab}"), ("token_squash", f"{head.lower()}{num}{ab}"),
                          ("token_hash", f"{head.upper()} #{num}{ab}"), ("token_zero", f"{head.lower()}-0{num}{ab}")):
            reformed = typed.replace(m.group(0), form, 1)
            if reformed != typed:
                out.append({"name": f"aliasing:{tag}", "text": text.replace(typed, reformed, 1),
                            "weakens_pin": True})
    return out
