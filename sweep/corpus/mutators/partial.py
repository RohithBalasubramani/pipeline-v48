"""mutators/partial.py — partial-name variants: users type 'DG-1', not 'DG-1 MFM' — head/tail halves, descriptor-word
drops (MFM/Panel/Feedbacks...), rating-suffix drops. All mangle the name -> weakens_pin."""
from __future__ import annotations

import random
import re

NAME = "partial"

_DESCRIPTORS = re.compile(r"\s+(mfm|panel|feedbacks?|meter|incomer)\b", re.IGNORECASE)
_SUFFIX = re.compile(r"\s*(CL:|\[).*$")                    # rating/site suffix users never type


def variants(text: str, ctx: dict, rng: random.Random) -> list[dict]:
    name = next((ctx[k] for k in ("asset", "panel") if ctx.get(k) and ctx[k] in text), None)
    if not name:
        return []
    cuts = []
    toks = name.split()
    if len(toks) >= 2:
        cuts.append(("partial_head", " ".join(toks[: max(1, len(toks) // 2)])))
        cuts.append(("partial_tail", " ".join(toks[-max(1, len(toks) // 2):])))
    no_desc = _DESCRIPTORS.sub("", name).strip()
    if no_desc and no_desc != name:
        cuts.append(("no_descriptor", no_desc))
    core = _SUFFIX.sub("", name).strip()
    if core and core != name:
        cuts.append(("no_suffix", core))
    return [{"name": f"partial:{n}", "text": text.replace(name, cut, 1), "weakens_pin": True}
            for n, cut in cuts if cut and cut != name]
