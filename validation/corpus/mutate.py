"""validation/corpus/mutate.py — spelling mutators for alias-robustness coverage: case, spacing, punctuation, partial
names, light typos. Each mutation returns (mutation_name, mutated_text) so coverage can slice pass-rate per mutation
kind. Mutations are TOLERANCE probes — the expectation stays 'cards|picker' (an honest picker on a mangled name is
correct behavior; a crash or a WRONG confident pin is the failure)."""
from __future__ import annotations

import random
import re


def mutations(name: str, rng: random.Random) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    out.append(("lowercase", name.lower()))
    out.append(("uppercase", name.upper()))
    out.append(("strip_punct", re.sub(r"[-_:]", " ", name)))
    out.append(("squash_space", re.sub(r"\s+", "", name)))
    toks = name.split()
    if len(toks) >= 2:
        out.append(("partial_head", " ".join(toks[: max(1, len(toks) // 2)])))
        out.append(("partial_tail", " ".join(toks[-max(1, len(toks) // 2):])))
    core = re.sub(r"\s*(CL:|\[).*$", "", name).strip()          # drop the rating/site suffix users never type
    if core and core != name:
        out.append(("no_suffix", core))
    letters = [i for i, ch in enumerate(name) if ch.isalpha()]
    if len(letters) > 4:
        i = rng.choice(letters[1:-1])
        out.append(("typo_drop", name[:i] + name[i + 1:]))
    rng.shuffle(out)
    return out
