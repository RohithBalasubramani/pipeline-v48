"""mutators/abbrev.py — abbreviation swaps from prompt_vocab: metric_abbrev ('power factor'->'pf', a routing probe,
pin untouched) and class_abbrev ('transformer'->'tfr' INSIDE an asset name, a resolution probe -> weakens_pin).
Vocab rows arrive via ctx['vocab'] (kind -> [{value, meta}]); meta = the canonical phrase the value replaces."""
from __future__ import annotations

import random
import re

NAME = "abbrev"


def _swaps(text: str, rows: list[dict], weakens: bool) -> list[dict]:
    out = []
    for row in rows or []:
        canonical, short = row["meta"], row["value"]
        if not canonical:
            continue
        pat = re.compile(re.escape(canonical), re.IGNORECASE)
        if pat.search(text):
            out.append({"name": f"abbrev:{canonical}->{short}", "text": pat.sub(short, text, count=1),
                        "weakens_pin": weakens})
    return out


def variants(text: str, ctx: dict, rng: random.Random) -> list[dict]:
    vocab = ctx.get("vocab") or {}
    return (_swaps(text, vocab.get("metric_abbrev"), weakens=False)
            + _swaps(text, vocab.get("class_abbrev"), weakens=True))
