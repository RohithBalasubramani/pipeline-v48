"""layer1b/compare/detect.py — does the prompt name TWO+ SPECIFIC assets to compare? (deterministic on the PROMPT).

The natural-compare gap: 'compare energy and power of GIC-01-N3-UPS-01 and GIC-02-N5-UPS-04' names TWO fully-specified
assets, but the single-asset AI resolver returns ONE confident pin OR one ambiguous list — it never splits the prompt,
so the collision gate sees BOTH UPS tokens, finds >1 uniquely-named hit, and falls to the single-asset picker (0 cards).

This detector finds the DISTINCT registry rows the prompt spells out FULLY, using the SAME discriminators the confident
single pin uses (`compare.discriminators._discriminators`: the whole registry name OR the unique GIC-node prefix 'gic-01-n3').
A row counts only when the prompt names it unambiguously — so:
  · 'GIC-01-N3-UPS-01 and GIC-02-N5-UPS-04'  → TWO distinct fully-named rows (ids 11, 23)     → a natural compare
  · bare 'UPS-01 and UPS-04'                 → ZERO fully-named rows (only class+unit tokens)  → NOT a compare here
    (each bare token collides across many rows → the per-name resolve stays ambiguous → the single picker fires)

Purely lexical + registry-driven; never calls the LLM. NOTE: `asset_candidates()` probes has_data over the live DB and
RAISES on an outage-shaped failure (honest data_unavailable, not fabricated has_data) — the host boundary
(host/multi_asset.natural_compare_ids) fail-opens that to the single path. `named_full_rows` returns the matched
candidate rows (asset_candidates shape) in prompt order, de-duplicated by registry id — the seed for the per-name resolve.
"""
from layer1b.resolve.asset_candidates import asset_candidates
from layer1b.compare.discriminators import _discriminators, _norm


def named_full_rows(prompt, cands=None):
    """The distinct registry rows the PROMPT names FULLY (whole name OR unique GIC-node prefix), in first-mention order,
    de-duplicated by canonical id. A row is included once per distinct id; a discriminator that matches >1 row (a shared
    GIC prefix would not — the prefix is unique — but a defensive guard) is skipped so only unambiguous full names count.
    Empty for a bare/implied prompt → the caller does NOT treat it as a natural compare."""
    cands = cands or asset_candidates()
    p = _norm(prompt)
    if not p:
        return []
    # position of the FIRST discriminator hit → order rows by where the user mentioned them (stable, human-readable)
    hits = []
    for c in cands:
        best = None
        for d in _discriminators(c[1]):
            if d and d in p:
                pos = p.find(d)
                best = pos if best is None else min(best, pos)
        if best is not None:
            hits.append((best, c))
    hits.sort(key=lambda x: x[0])
    out, seen = [], set()
    for _pos, c in hits:
        if c[0] not in seen:
            seen.add(c[0])
            out.append(c)
    return out


def is_natural_compare(prompt, cands=None):
    """True when the prompt spells out 2+ DISTINCT specific assets by full name/GIC-prefix — the natural-compare case
    the single-asset resolver drops. False for 0/1 named asset (single-asset path stays byte-identical)."""
    return len(named_full_rows(prompt, cands)) >= 2
