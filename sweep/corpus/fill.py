"""validation/corpus/fill.py — the SLOT ENGINE: ground one prompt_template row over the universe x vocab into base
cases. Slots: <metric> <asset> <asset1>..<asset5> <panel> <window> <class> <token> <scope> <concept> <offdomain>
<invalid>. DETERMINISTIC + explosion-safe: per-template rng (seed:tkey) + mixed-radix INDEX sampling over the slot
product space (never materializes a cartesian), capped at the caller's base budget. Class-appropriateness is enforced
post-decode: a binding whose <metric> doesn't apply to the bound asset's class is discarded ('fuel for a chiller' is
the invalid CATEGORY's job, never an accident here)."""
from __future__ import annotations

import hashlib
import re
from itertools import combinations, islice
from random import Random

from sweep.corpus.store import metrics_for

_SLOT = re.compile(r"<(\w+)>")
_OVERSAMPLE = 3          # sampled indices per surviving base (metric-class filtering discards some)


def case(category: str, prompt: str, expect: str, **meta) -> dict:
    cid = hashlib.sha1(f"{category}|{prompt}".encode("utf-8", "replace")).hexdigest()[:12]
    return {"id": cid, "category": category, "prompt": prompt, "expect": expect,
            "meta": {k: v for k, v in meta.items() if v not in (None, "", [])}}


def _short_token(name: str) -> str | None:
    """The class+unit shorthand a user types — the LAST unit token, not the first: 'GIC-21-N4-UPS-08' -> 'UPS-8'
    (the leading site prefix is what users OMIT)."""
    ms = re.findall(r"([A-Za-z]{2,12})[\s\-_]*0?(\d{1,2})([ab]?)\b", name)
    return f"{ms[-1][0].upper()}-{ms[-1][1]}{ms[-1][2]}" if ms else None


def _asset_entries(u: dict, short: bool) -> list[tuple[str, dict]]:
    out = []
    for a in u["unique_names"]:
        typed = _short_token(a["name"]) if short else a["name"]
        if typed:
            out.append((typed, {"asset": typed, "asset_canonical": a["name"], "cls": a["cls"]}))
    return out


def _panel_entries(u: dict) -> list[tuple[str, dict]]:
    groups: dict[str, list[str]] = {}
    for alias, canonical in u["panel_aliases"]:
        groups.setdefault(canonical, []).append(alias)
    out = []
    for canonical in sorted(groups):
        siblings = sorted(groups[canonical])
        for a in siblings:
            out.append((a, {"panel": a, "panel_canonical": canonical, "cls": "Panel",
                            "aliases": [x for x in siblings if x != a]}))
    return out


def _pools(slots: list[str], category: str, u: dict, vocab: dict) -> list[list[tuple[str, dict]]] | None:
    """One (text, meta-updates) pool per slot occurrence; None = a slot has no rows (template yields nothing)."""
    def lane(kind, **extra):
        return [(r["value"], dict(extra)) for r in vocab.get(kind, [])]

    pools = []
    for s in slots:
        if s == "asset":
            p = _asset_entries(u, short=(category == "alias"))
        elif s == "panel":
            p = _panel_entries(u)
        elif s == "metric":
            p = [(r["value"], {"metric": r["value"]}) for r in vocab.get("metric", [])]
        elif s == "window":
            p = [(r["value"], {"window": r["value"]}) for r in vocab.get("window", [])]
        elif s == "scope":
            p = [(r["value"], {"scope": "incomer"}) for r in vocab.get("scope_incomer", [])]
        elif s == "class":
            p = [(c.lower(), {"cls": c}) for c in sorted(u["by_class"]) if c != "Load"]
        elif s == "token":
            p = [(t, {"token": t}) for t in u["homonym_tokens"]]
        elif s == "concept":
            p = lane("concept")
        elif s == "offdomain":
            p = lane("off_domain")
        elif s == "invalid":
            p = lane("invalid_asset")
        else:                                              # unknown slot -> loud, not silent (seed typo)
            raise ValueError(f"prompt_template slot <{s}> has no fill rule")
        if not p:
            return None
        pools.append(p)
    return pools


def _decode(idx: int, pools: list[list]) -> list[tuple[str, dict]]:
    picks = []
    for pool in pools:
        idx, r = divmod(idx, len(pool))
        picks.append(pool[r])
    return picks


def _fill_slotted(tmpl: dict, expect: str, u: dict, vocab: dict, rng: Random, cap: int) -> list[dict]:
    slots = _SLOT.findall(tmpl["template"])
    pools = _pools(slots, tmpl["category"], u, vocab)
    if pools is None:
        return []
    total = 1
    for p in pools:
        total *= len(p)
    n_idx = min(total, cap * _OVERSAMPLE)
    indices = range(total) if total <= n_idx else sorted(rng.sample(range(total), n_idx))

    out = []
    for idx in indices:
        picks = _decode(idx, pools)
        meta: dict = {"template": tmpl["tkey"]}
        for _, m in picks:
            meta.update(m)
        # class-appropriateness: discard bindings whose metric can't serve the bound class
        if meta.get("metric") and meta.get("cls") and meta["metric"] not in metrics_for(meta["cls"], vocab):
            continue
        prompt = tmpl["template"]
        for s, (text, _) in zip(slots, picks):
            prompt = prompt.replace(f"<{s}>", text, 1)
        out.append(case(tmpl["category"], prompt, expect, **meta))
        if len(out) >= cap:
            break
    return out


def _fill_compare(tmpl: dict, expect: str, u: dict, vocab: dict, rng: Random, cap: int) -> list[dict]:
    slots = _SLOT.findall(tmpl["template"])
    n = max(int(s[5:]) for s in slots if s.startswith("asset"))
    uniq_ids = {a["id"] for a in u["unique_names"]}
    by_cls = {c: [a for a in pool if a["id"] in uniq_ids] for c, pool in sorted(u["by_class"].items())}
    metric_in = "metric" in slots

    def build(assets, cls):
        prompt = tmpl["template"]
        for i, a in enumerate(assets, 1):
            prompt = prompt.replace(f"<asset{i}>", a["name"], 1)
        meta = {"template": tmpl["tkey"], "assets": [a["name"] for a in assets], "cls": cls}
        if metric_in:
            m = rng.choice(metrics_for(cls, vocab) or ["energy and power"])
            prompt = prompt.replace("<metric>", m, 1)
            meta["metric"] = m
        return case(tmpl["category"], prompt, expect, **meta)

    out = []
    if tmpl["category"] == "compare_mixed":
        classes = [c for c, p in by_cls.items() if p and c != "Load"]
        pairs = list(combinations(classes, 2))
        quota = max(1, -(-cap // max(1, len(pairs))))
        for ca, cb in pairs:
            for a, b in islice(zip(by_cls[ca], by_cls[cb]), quota):
                out.append(build([a, b], f"{ca}+{cb}"))
    else:
        eligible = [c for c, p in by_cls.items() if len(p) >= n]
        quota = max(1, -(-cap // max(1, len(eligible))))
        for cls in eligible:
            for combo in islice(combinations(by_cls[cls], n), quota):
                out.append(build(list(combo), cls))
    return out[:cap]


def ground(tmpl: dict, expect: str, u: dict, vocab: dict, seed: int, cap: int) -> list[dict]:
    """All base cases for one template row, capped at `cap` (deterministic under seed:tkey)."""
    rng = Random(f"{seed}:{tmpl['tkey']}")
    if any(s.startswith("asset") and s != "asset" for s in _SLOT.findall(tmpl["template"])):
        return _fill_compare(tmpl, expect, u, vocab, rng, cap)
    return _fill_slotted(tmpl, expect, u, vocab, rng, cap)
