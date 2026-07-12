"""validation/corpus/mutate.py — the MUTATION COMPOSER. Two entry points:

  mutations(name, rng)      the ORIGINAL name-mangle probe set (kept verbatim — the 'mutated' category's lane, so its
                            pass-rate series stays comparable across corpus versions);
  expand_case(case, ...)    the DB-driven expansion: every enabled mutator family (mutators/ registry) over a base
                            case -> deduped variant cases, DETERMINISTIC per case (rng sub-seeded from seed+case id, so
                            adding templates/rows never reshuffles existing cases' variants).

Mutations are TOLERANCE probes — a variant whose mutator declares weakens_pin=True gets its expect widened with
'|picker' (an honest picker on a mangled name is correct behavior; a crash or a WRONG confident pin is the failure).
Wrapper/casing variants keep the base expect: if 'please show me energy for DG-1' pickers, that IS a defect."""
from __future__ import annotations

import hashlib
import random
import re

from sweep.corpus.mutators import REGISTRY, SAFE_WITHOUT_ASSET, enabled_mutators


def mutations(name: str, rng: random.Random) -> list[tuple[str, str]]:
    """The original name-mangle probe set (case, spacing, punctuation, partials, light typos) — unchanged."""
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


def _widen(expect: str) -> str:
    """cards/compare expectations tolerate an honest picker once the name is mangled; terminal lanes stay strict."""
    if "picker" in expect:
        return expect
    if any(t.startswith(("cards", "compare")) for t in expect.split("|")):
        return expect + "|picker"
    return expect


def _variant_case(base: dict, text: str, mutation: str, expect: str) -> dict:
    cid = hashlib.sha1(f"{base['category']}|{text}".encode("utf-8", "replace")).hexdigest()[:12]
    return {"id": cid, "category": base["category"], "prompt": text, "expect": expect,
            "meta": {**(base.get("meta") or {}), "mutation": mutation, "base_id": base["id"]}}


def expand_case(base: dict, vocab: dict, seed: int, k: int | None = None) -> list[dict]:
    """Up to k mutation-variant cases of `base` (k = corpus.mutations_per_case). Mutator exceptions PROPAGATE —
    a broken family must fail generation loudly, never silently thin the corpus."""
    if k is None:
        from config.app_config import cfg
        k = int(cfg("corpus.mutations_per_case", 11))
    meta = base.get("meta") or {}
    has_name = bool(meta.get("asset") or meta.get("panel"))
    ctx = {**meta, "vocab": vocab}
    rng = random.Random(f"{seed}:{base['id']}")

    pool, seen = [], {base["prompt"]}
    for mname in enabled_mutators():
        if not has_name and mname not in SAFE_WITHOUT_ASSET:
            continue
        for v in REGISTRY[mname].variants(base["prompt"], ctx, rng):
            if v["text"] not in seen:
                seen.add(v["text"])
                pool.append(v)
    pool.sort(key=lambda v: (v["name"], v["text"]))
    chosen = pool if len(pool) <= k else rng.sample(pool, k)
    return [_variant_case(base, v["text"], v["name"],
                          _widen(base["expect"]) if v["weakens_pin"] else base["expect"])
            for v in chosen]
