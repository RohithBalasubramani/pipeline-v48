"""validation/corpus/generate.py — DB-DRIVEN corpus generation: prompt_template x universe x prompt_vocab, multiplied
through the mutation engine, downsampled to each prompt_category budget (JSONL, one case per line).

DETERMINISTIC three ways: template grounding is rng(seed:tkey) + index-sampled (fill.py); mutation expansion is
rng(seed:case_id) (mutate.py); budget downsampling is rng(seed:category). Every stream is sub-seeded from corpus.seed
+ a stable key, so ADDING a template/vocab row grows the corpus without reshuffling existing cases — corpus diffs mean
the DB rows or the universe changed, not the generator's mood.

Case shape (the runner/judge contract, unchanged): {id, category, prompt, expect, meta} — id = sha1(category|prompt),
meta carries {template, asset/panel/cls/metric/window/scope/token, mutation, base_id} for coverage slicing.

Scale: category budgets (DB rows) sum to ~31k by default — the 'tens of thousands' dial is `UPDATE prompt_category
SET budget=...`, no code edit. Per-category shortfalls (pool smaller than budget) are REPORTED by stats(), never
silently padded."""
from __future__ import annotations

import json
import random

from config.app_config import cfg
from sweep.corpus import fill
from sweep.corpus.mutate import expand_case, mutations
from sweep.corpus.store import store
from sweep.corpus.universe import universe

_BASE_SHARE = 4          # bases generated per unit budget (each base yields ~mutations_per_case variants + itself)


def _base_caps(s: dict) -> dict[str, int]:
    """tkey -> base-case cap: the category budget split across its templates by weight, deflated by _BASE_SHARE."""
    wsum: dict[str, int] = {}
    for t in s["templates"]:
        wsum[t["category"]] = wsum.get(t["category"], 0) + t["weight"]
    caps = {}
    for t in s["templates"]:
        cat = s["categories"].get(t["category"])
        if cat:
            caps[t["tkey"]] = max(8, -(-cat["budget"] * t["weight"] // (wsum[t["category"]] * _BASE_SHARE)))
    return caps


def _mangle_lane(base: dict, seed: int) -> list[dict]:
    """The 'mutated' category's classic name-mangle probes (mutations() — its own lane, not the standard engine)."""
    asset = (base.get("meta") or {}).get("asset") or ""
    if not asset or asset not in base["prompt"]:
        return []
    rng = random.Random(f"{seed}:mangle:{base['id']}")
    out = []
    for mut_name, mutated in mutations(asset, rng)[:4]:
        if mutated and mutated != asset:
            out.append(fill.case(base["category"], base["prompt"].replace(asset, mutated, 1), base["expect"],
                                 **{**base["meta"], "mutation": mut_name, "base_id": base["id"]}))
    return out


def generate() -> list[dict]:
    s = store()
    u = universe()
    seed = int(cfg("corpus.seed", 48))
    k = int(cfg("corpus.mutations_per_case", 11))
    caps = _base_caps(s)

    # ground every enabled template over the universe
    bases: list[dict] = []
    for tmpl in s["templates"]:
        cat = s["categories"].get(tmpl["category"])
        if not cat or tmpl["tkey"] not in caps:
            continue
        expect = tmpl["expect"] or cat["expect"]
        bases.extend(fill.ground(tmpl, expect, u, s["vocab"], seed, caps[tmpl["tkey"]]))

    # multiply through the mutation engine ('mutated' keeps its classic mangle lane)
    pool: list[dict] = []
    for b in bases:
        pool.append(b)
        pool.extend(_mangle_lane(b, seed) if b["category"] == "mutated" else expand_case(b, s["vocab"], seed, k))

    # dedupe (same category+prompt == same id), then per-category budget downsample, stable global order
    by_id: dict[str, dict] = {}
    for c in pool:
        by_id.setdefault(c["id"], c)
    by_cat: dict[str, list[dict]] = {}
    for c in by_id.values():
        by_cat.setdefault(c["category"], []).append(c)

    out: list[dict] = []
    for cat in sorted(by_cat):
        rows = sorted(by_cat[cat], key=lambda c: c["id"])
        budget = s["categories"][cat]["budget"]
        out.extend(rows if len(rows) <= budget else random.Random(f"{seed}:{cat}").sample(rows, budget))
    out.sort(key=lambda c: (c["category"], c["id"]))
    return out


def write(path: str) -> int:
    cases = generate()
    import os
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        for c in cases:
            f.write(json.dumps(c, sort_keys=True) + "\n")
    return len(cases)
