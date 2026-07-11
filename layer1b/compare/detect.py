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

_ALIAS_IDX = {}


def _panel_alias_index():
    """{normalized panel_name -> [RAW alias, ...]} from cmd_catalog.pcc_panel_alias — the PCC-panel aliases a user
    actually types ('pcc-1a', 'panel-2a', 'panel-2') instead of the canonical registry name ('PCC-Panel-2'). Lets the
    compare detector recognize a panel NAMED BY ALIAS ('compare pcc panel 1a and panel 2a' spells out 2 panels — the
    registry name never appears in that prompt), and lets the sub-prompt splitter (resolve_names._span_regex) STRIP an
    alias-typed name. RAW aliases (normalize at use): the splitter needs the alias's own tokens to build a tolerant
    regex ('pcc-2a' -> pcc[-_ ]*2a matches 'PCC-2A'; a pre-normalized 'pcc2a' could not). Process-cached; {} on any
    failure (fail-open — name-only detection still works). [compare-alias fix]"""
    if _ALIAS_IDX:
        return _ALIAS_IDX
    try:
        from data.db_client import q
        for pname, alias in q("cmd_catalog", "SELECT panel_name, alias FROM pcc_panel_alias WHERE panel_name IS NOT NULL"):
            if pname and alias:
                _ALIAS_IDX.setdefault(_norm(pname), []).append(str(alias))
    except Exception:
        pass
    return _ALIAS_IDX


def named_full_rows(prompt, cands=None):
    """The distinct registry rows the PROMPT names FULLY (whole name OR unique GIC-node prefix), in first-mention order,
    de-duplicated by canonical id. A row is included once per distinct id; a discriminator that matches >1 row (a shared
    GIC prefix would not — the prefix is unique — but a defensive guard) is skipped so only unambiguous full names count.
    Empty for a bare/implied prompt → the caller does NOT treat it as a natural compare."""
    cands = cands or asset_candidates()
    p = _norm(prompt)
    if not p:
        return []
    # position + LENGTH of each row's best (longest) discriminator hit → order rows by first mention AND drop a row
    # whose every hit is an INFIX of another row's longer hit [phantom-alias fix]: 'Chiller Panel-1 Main INC' contains
    # the PCC alias 'panel1', so the PCC-Panel-1 row false-hit INSIDE the chiller's name — a 5-chiller compare detected
    # 9 rows, the phantom panels' sub-prompts resolved empty, and the whole compare silently degraded to single.
    # A hit only counts as its OWN mention when its span is NOT strictly contained in a longer row's span.
    aidx = _panel_alias_index()
    hits = []
    for c in cands:
        spans = []
        # registry-name discriminators + this panel's typed aliases ('pcc-1a'/'panel-2a') so an alias-named panel counts
        discs = list(_discriminators(c[1])) + [_norm(a) for a in aidx.get(_norm(c[1]), [])]
        for d in discs:
            if d and d in p:
                start = p.find(d)
                spans.append((start, start + len(d)))
        if spans:
            hits.append((spans, c))
    # longest hit per row; a row survives only if SOME hit of its is not strictly inside another row's longer hit
    def _contained(s, others):
        return any(o[0] <= s[0] and s[1] <= o[1] and (o[1] - o[0]) > (s[1] - s[0]) for o in others)
    all_spans = [s for spans, _c in hits for s in spans]
    kept = []
    for spans, c in hits:
        own = [s for s in spans if not _contained(s, [o for o in all_spans if o not in spans])]
        if own:
            kept.append((min(s[0] for s in own), c))
    kept.sort(key=lambda x: x[0])
    out, seen = [], set()
    for _pos, c in kept:
        if c[0] not in seen:
            seen.add(c[0])
            out.append(c)
    return out


def is_natural_compare(prompt, cands=None):
    """True when the prompt spells out 2+ DISTINCT specific assets by full name/GIC-prefix — the natural-compare case
    the single-asset resolver drops. False for 0/1 named asset (single-asset path stays byte-identical)."""
    return len(named_full_rows(prompt, cands)) >= 2
