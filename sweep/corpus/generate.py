"""validation/corpus/generate.py — permute templates x universe into the CORPUS (JSONL, one case per line).
DETERMINISTIC: seeded RNG (seed=48) + stable ordering + stable case ids (sha1 of category+prompt), so two generations
over the same universe are byte-identical — corpus diffs mean the UNIVERSE changed, not the generator's mood.

Case shape: {id, category, prompt, expect, meta:{asset, cls, metric, window, mutation}} — meta drives coverage."""
from __future__ import annotations

import hashlib
import json
import random

from validation.corpus.templates import METRICS, TIME_WINDOWS, CONCEPTS, OFF_DOMAIN, INVALID, CATEGORIES
from validation.corpus.universe import universe
from validation.corpus.mutate import mutations


def _case(category: str, prompt: str, expect: str, **meta) -> dict:
    cid = hashlib.sha1(f"{category}|{prompt}".encode("utf-8", "replace")).hexdigest()[:12]
    return {"id": cid, "category": category, "prompt": prompt, "expect": expect, "meta": meta}


def _metrics_for(cls: str):
    return [m for m, classes in METRICS.items() if classes is None or cls in classes]


def generate() -> list[dict]:
    rng = random.Random(48)
    u = universe()
    cases: list[dict] = []
    uniq = u["unique_names"]

    def take(pool, n):
        pool = sorted(pool, key=lambda a: a["id"])
        return pool if len(pool) <= n else rng.sample(pool, n)

    # single_asset + historical + narrative + sld/3d/sankey — over UNIQUE (confidently-resolvable) names
    for a in uniq:
        for m in _metrics_for(a["cls"]):
            cases.append(_case("single_asset", f"{m} for {a['name']}", CATEGORIES["single_asset"]["expect"],
                               asset=a["name"], cls=a["cls"], metric=m))
    for a in take(uniq, 90):
        for w in TIME_WINDOWS:
            m = rng.choice(_metrics_for(a["cls"]) or ["energy and power"])
            cases.append(_case("historical", f"{m} for {a['name']} {w}", CATEGORIES["historical"]["expect"],
                               asset=a["name"], cls=a["cls"], metric=m, window=w))
    for a in take(uniq, 20):
        cases.append(_case("narrative", f"give me a summary of {a['name']}", CATEGORIES["narrative"]["expect"],
                           asset=a["name"], cls=a["cls"]))

    # panel-aggregate via aliases (+ incomer scope) / sld / 3d / sankey over panels
    aliases = [al for al, _ in u["panel_aliases"]]
    for al in aliases:
        cases.append(_case("panel_aggregate", f"energy and power for {al}", CATEGORIES["panel_aggregate"]["expect"], asset=al, cls="Panel"))
        cases.append(_case("panel_aggregate", f"voltage and current for incomer {al}", CATEGORIES["panel_aggregate"]["expect"], asset=al, cls="Panel", scope="incomer"))
        cases.append(_case("alias", f"real time monitoring for {al.lower()}", CATEGORIES["alias"]["expect"], asset=al, cls="Panel"))
    for al in aliases[:8]:
        cases.append(_case("sld", f"single line diagram for {al}", CATEGORIES["sld"]["expect"], asset=al, cls="Panel"))
        cases.append(_case("view_3d", f"3d view of {al}", CATEGORIES["view_3d"]["expect"], asset=al, cls="Panel"))
        cases.append(_case("sankey", f"energy flow distribution for {al}", CATEGORIES["sankey"]["expect"], asset=al, cls="Panel"))

    # compare — 2/3/5 same-class, mixed-class, alias + full-name spellings
    for cls, pool in sorted(u["by_class"].items()):
        up = [a for a in pool if a in uniq]
        if len(up) >= 2:
            a, b = up[0], up[1]
            cases.append(_case("compare_2", f"compare {a['name']} and {b['name']} power", CATEGORIES["compare_2"]["expect"], cls=cls, assets=[a["name"], b["name"]]))
        if len(up) >= 3:
            a, b, c = up[0], up[1], up[2]
            cases.append(_case("compare_3", f"compare {a['name']} and {b['name']} and {c['name']} energy", CATEGORIES["compare_3"]["expect"], cls=cls, assets=[a["name"], b["name"], c["name"]]))
        if len(up) >= 5:
            names = " and ".join(x["name"] for x in up[:5])
            cases.append(_case("compare_5", f"compare {names} energy", CATEGORIES["compare_5"]["expect"], cls=cls))
    pa = [al for al, _ in u["panel_aliases"]][:6]
    for i in range(0, len(pa) - 1, 2):
        cases.append(_case("compare_2", f"compare {pa[i]} and {pa[i+1]} energy", CATEGORIES["compare_2"]["expect"], cls="Panel", assets=[pa[i], pa[i+1]]))
    mixed_pairs = [(u["by_class"].get("DG", [None])[0], u["by_class"].get("UPS", [None])[0]),
                   (u["by_class"].get("Transformer", [None])[0], u["by_class"].get("Panel", [None])[0])]
    for a, b in mixed_pairs:
        if a and b:
            cases.append(_case("compare_mixed", f"compare {a['name']} and {b['name']} energy", CATEGORIES["compare_mixed"]["expect"], assets=[a["name"], b["name"]]))

    # ambiguity — bare homonym tokens + bare classes
    for t in u["homonym_tokens"]:
        cases.append(_case("ambiguous", f"show me the dashboard for {t}", CATEGORIES["ambiguous"]["expect"], token=t))
    for cls in ("Transformer", "UPS", "Chiller", "Panel", "AHU", "Pump"):
        cases.append(_case("ambiguous", f"voltage for {cls.lower()}", CATEGORIES["ambiguous"]["expect"], cls=cls))

    # invalid / knowledge / off-domain — fixed lists
    for p in INVALID:
        cases.append(_case("invalid", p, CATEGORIES["invalid"]["expect"]))
    for p in CONCEPTS:
        cases.append(_case("knowledge", p, CATEGORIES["knowledge"]["expect"]))
    for p in OFF_DOMAIN:
        cases.append(_case("off_domain", p, CATEGORIES["off_domain"]["expect"]))

    # mutated spellings of unique names (alias-robustness)
    for a in take(uniq, 20):
        for mut_name, mutated in mutations(a["name"], rng)[:3]:
            cases.append(_case("mutated", f"voltage and current for {mutated}", CATEGORIES["mutated"]["expect"],
                               asset=a["name"], cls=a["cls"], mutation=mut_name))

    # mixed multi-intent
    for a in take(uniq, 10):
        cases.append(_case("mixed", f"energy and power for {a['name']} last week and summarize anomalies",
                           CATEGORIES["mixed"]["expect"], asset=a["name"], cls=a["cls"]))

    # deterministic per-category downsample to each category's budget + stable global order
    by_cat: dict[str, list[dict]] = {}
    for c in cases:
        by_cat.setdefault(c["category"], []).append(c)
    out: list[dict] = []
    for cat in sorted(by_cat):
        pool = sorted(by_cat[cat], key=lambda c: c["id"])
        budget = CATEGORIES[cat]["count"]
        out.extend(pool if len(pool) <= budget else random.Random(f"48:{cat}").sample(pool, budget))
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
