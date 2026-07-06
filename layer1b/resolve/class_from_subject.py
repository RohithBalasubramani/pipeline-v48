"""layer1b/resolve/class_from_subject.py — infer the asset CLASS from the prompt subject/metric (concept → class).

A deterministic PRIOR that narrows the candidate listing BEFORE the AI asset-resolve call, so a bare/implied class
('the UPS', 'battery backup', 'genset load') with no unit number is filtered to the right equipment class instead of
the AI having to reason over all 310 rows (fewer ambiguous outcomes). This is ADDITIVE to asset_resolve — it never
pins a single meter, only supplies a class filter. [RN-06 class-from-concept inference; covers TOPO-07/RN-06]

POLICY, not hardcoded facts:
  · the valid class SET is read LIVE from the registry (asset_candidates distinct classes) — this file can NEVER emit a
    class that doesn't physically exist, and new classes appear automatically.
  · the hint grammar is DB-DRIVEN (cmd_catalog.app_config key 'layer1b.class_concept_hints', json) with the
    `_CONCEPT_HINTS` dict below as the code-default fallback — one dedicated place, no magic strings in logic.

TWO-PASS RULE (hardening: the DG-1→UPS root cause): each class declares
  · tokens   — EXPLICIT equipment-class words ('dg', 'ups', 'transformer'). An explicit token ALWAYS outranks any
               ambient concept word, regardless of declaration order ('dg operations and runtime' is DG, even though
               'runtime' is also a concept hint elsewhere).
  · concepts — ambient domain words ('battery', 'fuel', 'tap') consulted ONLY when no explicit token hit.
When MORE THAN ONE class hits within the deciding pass, the prior returns None (do NOT narrow — the AI resolves over
the full listing, which the A/B test proved it does correctly). The old first-declared-class-wins scan silently
narrowed DG prompts to UPS because 'runtime' sat in the UPS list.
"""
import re

from config.app_config import cfg
from layer1b.resolve.asset_candidates import asset_candidates

# ── the ONE editable policy (code-default; live value = app_config 'layer1b.class_concept_hints') ───────────────────
# {class: {"tokens": [explicit class words], "concepts": [ambient concept words]}} — class labels as produced by
# asset_candidates' _CLASS_SQL so the two vocabularies stay aligned. Edit the DB row (preferred) or here to retune.
_CONCEPT_HINTS = {
    "UPS":         {"tokens": ["ups"],
                    "concepts": ["battery", "backup", "autonomy", "inverter", "rectifier"]},
    "DG":          {"tokens": ["dg", "diesel", "genset", "generator"],
                    "concepts": ["fuel", "engine", "runtime"]},   # runtime = DG-ops concept here (page operations-runtime)
    "Transformer": {"tokens": ["transformer", "xformer", "tf"],
                    "concepts": ["tap", "winding", "oil temp", "oil-temp", "hv-lv", "hvlv"]},
    "APFCR":       {"tokens": ["apfc", "apfcr"],
                    "concepts": ["capacitor", "kvar", "power factor bank", "pf bank", "reactive comp"]},
    "Incomer":     {"tokens": ["incomer", "incoming"],
                    "concepts": ["11kv", "ht incomer", "grid incomer"]},
    "AHU":         {"tokens": ["ahu"],
                    "concepts": ["air handling", "air-handling"]},
    "AirWasher":   {"tokens": ["airwasher", "air washer", "air-washer"], "concepts": []},
    "Chiller":     {"tokens": ["chiller"], "concepts": []},        # feeds the feeder_generic route [BATCH D #14]
    "Pump":        {"tokens": ["pump"], "concepts": []},
    "Compressor":  {"tokens": ["compressor"], "concepts": []},     # feeds the feeder_generic route [BATCH D #14]
    "Fan":         {"tokens": ["fan"], "concepts": ["exhaust", "blower"]},
    "Feeder":      {"tokens": ["feeder"], "concepts": ["outgoing"]},
    "Panel":       {"tokens": ["pcc", "mcc", "bpdb", "mldb", "pdb", "panel"],
                    "concepts": ["busbar", "bus bar", "distribution board"]},
    "Spare":       {"tokens": ["spare"], "concepts": []},
}


def _hints():
    """The live policy: DB row (json, same shape) else the code default. Malformed DB rows fall back per-key."""
    h = cfg("layer1b.class_concept_hints", _CONCEPT_HINTS)
    return h if isinstance(h, dict) and h else _CONCEPT_HINTS


def _known_classes():
    """The class labels that ACTUALLY exist in the live registry — the concept prior is clamped to this set so it can
    never bias the AI toward a class with zero meters. fail-open: on a registry read error, allow every hint class."""
    try:
        return {c[5] for c in asset_candidates() if c[5]}
    except Exception:
        return set(_hints())


def _hit(text, kw):
    """word-ish boundary: keyword surrounded by non-alphanumerics in the normalized text."""
    return re.search(r"(?<![a-z0-9])" + re.escape(kw.lower()) + r"(?![a-z0-9])", text) is not None


def class_from_subject(prompt):
    """Return the single most-likely equipment CLASS for a prompt, or None when the subject implies no class OR when
    the class is AMBIGUOUS (>1 class hits in the deciding pass — the resolver then runs unfiltered over the full
    listing). Explicit class tokens outrank concept words. Never raises; None on empty/unmatched input."""
    if not prompt:
        return None
    text = " " + re.sub(r"[^a-z0-9]+", " ", str(prompt).lower()) + " "
    known = _known_classes()
    hints = _hints()
    for pass_key in ("tokens", "concepts"):                        # pass 1: explicit tokens; pass 2: ambient concepts
        hit_classes = []
        for cls, kws in hints.items():
            if known and cls not in known:
                continue
            if any(_hit(text, k) for k in (kws or {}).get(pass_key, []) if k):
                hit_classes.append(cls)
        if len(hit_classes) == 1:
            return hit_classes[0]
        if len(hit_classes) > 1:
            return None                                            # ambiguous — do NOT narrow (full listing to the AI)
    return None


def candidates_of_class(cands, cls):
    """The subset of `cands` (asset_candidates rows) whose class == `cls`. When `cls` is None OR no row matches, returns
    the FULL list unchanged (fail-open — the prior only narrows, it never empties the pool)."""
    if not cls:
        return cands
    sub = [c for c in cands if c[5] == cls]
    return sub or cands
