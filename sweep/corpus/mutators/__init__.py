"""validation/corpus/mutators/ — the MUTATION FAMILIES that multiply base cases into robustness variants (one
single-purpose module per family). Contract per module:

    NAME: str
    variants(text, ctx, rng) -> list[{"name": str, "text": str, "weakens_pin": bool}]

`ctx` is the base case's meta (asset/panel/metric/cls/aliases...). `weakens_pin=True` marks a variant that mangles the
ASSET NAME itself — the generator widens its expect with '|picker' (an honest picker on a mangled name is correct
behavior; a WRONG confident pin or a crash is the failure — see mutate.py). Enabled set = cfg('corpus.mutators')."""
from __future__ import annotations

from sweep.corpus.mutators import abbrev, aliasing, casing, conversational, partial, plural, spelling

_ALL = ["casing", "spelling", "abbrev", "partial", "plural", "aliasing", "conversational"]
REGISTRY = {m.NAME: m for m in (casing, spelling, abbrev, partial, plural, aliasing, conversational)}

# families safe for cases with NO asset/panel in the prompt (knowledge/off_domain/invalid/ambiguous):
# name-mangling families need a name to mangle and would only add noise there.
SAFE_WITHOUT_ASSET = {"casing", "conversational"}


def enabled_mutators() -> list[str]:
    from config.app_config import cfg
    names = cfg("corpus.mutators", _ALL)
    return [n for n in names if n in REGISTRY]
