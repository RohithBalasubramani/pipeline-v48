"""layer1b/resolve/class_from_subject.py — infer the asset CLASS from the prompt subject/metric (concept → class).

A deterministic PRIOR that narrows the candidate listing BEFORE the AI asset-resolve call, so a bare/implied class
('the UPS', 'battery backup', 'genset load') with no unit number is filtered to the right equipment class instead of
the AI having to reason over all 310 rows (fewer ambiguous outcomes). This is ADDITIVE to asset_resolve — it never
pins a single meter, only supplies a class filter. [RN-06 class-from-concept inference; covers TOPO-07/RN-06]

POLICY, not hardcoded facts:
  · the valid class SET is read LIVE from the registry (asset_candidates distinct classes) — this file can NEVER emit a
    class that doesn't physically exist, and new classes appear automatically.
  · the concept→class hint grammar is the SINGLE editable policy dict `_CONCEPT_HINTS` below (same vocabulary the
    asset_system.md prompt encodes) — one dedicated place, documented, no magic strings scattered in logic.
"""
import re

from layer1b.resolve.asset_candidates import asset_candidates

# ── the ONE editable policy: metric/concept keyword → canonical equipment class ─────────────────────────────────────
# Keys are word-boundary keywords found in a prompt; the value is the class label as produced by asset_candidates'
# _CLASS_SQL (so the two vocabularies stay aligned). Order does not matter — first CLASS whose any keyword hits wins by
# the scan order of _CONCEPT_HINTS.items(); a tie keeps the earliest-declared class. Edit here to retune the prior.
_CONCEPT_HINTS = {
    "UPS":         ["ups", "battery", "backup", "autonomy", "runtime", "inverter", "rectifier"],
    "DG":          ["dg", "diesel", "genset", "generator", "fuel", "engine"],
    "Transformer": ["transformer", "xformer", "tap", "winding", "oil temp", "oil-temp", "hv-lv", "hvlv", "tf-", "tf "],
    "APFCR":       ["apfc", "apfcr", "capacitor", "kvar", "power factor bank", "pf bank", "reactive comp"],
    "Incomer":     ["incomer", "incoming", "11kv", "ht incomer", "grid incomer"],
    "AHU":         ["ahu", "air handling", "air-handling"],
    "AirWasher":   ["air washer", "air-washer", "airwasher"],
    "Chiller":     ["chiller"],
    "Pump":        ["pump"],
    "Compressor":  ["compressor"],
    "Fan":         ["fan", "exhaust", "blower"],
    "Feeder":      ["feeder", "outgoing"],
    "Panel":       ["pcc", "mcc", "bpdb", "mldb", "pdb", "busbar", "bus bar", "distribution board", "panel"],
    "Spare":       ["spare"],
}


def _known_classes():
    """The class labels that ACTUALLY exist in the live registry — the concept prior is clamped to this set so it can
    never bias the AI toward a class with zero meters. fail-open: on a registry read error, allow every hint class."""
    try:
        return {c[5] for c in asset_candidates() if c[5]}
    except Exception:
        return set(_CONCEPT_HINTS)


def class_from_subject(prompt):
    """Return the single most-likely equipment CLASS for a prompt, or None when the subject implies no class (so the
    resolver runs unfiltered). Pure keyword scan over `_CONCEPT_HINTS`, clamped to classes present in the registry.
    Never raises; None on empty/unmatched input."""
    if not prompt:
        return None
    text = " " + re.sub(r"[^a-z0-9]+", " ", str(prompt).lower()) + " "
    known = _known_classes()
    for cls, kws in _CONCEPT_HINTS.items():
        if known and cls not in known:
            continue
        for kw in kws:
            k = kw.lower()
            # word-ish boundary: keyword surrounded by non-alphanumerics in the normalized text
            if re.search(r"(?<![a-z0-9])" + re.escape(k) + r"(?![a-z0-9])", text):
                return cls
    return None


def candidates_of_class(cands, cls):
    """The subset of `cands` (asset_candidates rows) whose class == `cls`. When `cls` is None OR no row matches, returns
    the FULL list unchanged (fail-open — the prior only narrows, it never empties the pool)."""
    if not cls:
        return cands
    sub = [c for c in cands if c[5] == cls]
    return sub or cands
