"""layer1b/guardrail/spelling_recovery.py — difflib fuzzy recovery for paraphrased/typo'd asset NAMES. [hardening]

The asset prompt orders the model to copy names VERBATIM, but a paraphrased/typo'd emission ('DG-1 MFM ' → 'DG1 MFM',
'Transformer 05' → 'Transformer-05 SE') used to be silently DROPPED by the exact+normalized resolver, collapsing an
explicit asset ask into how='empty'. This guardrail fuzzy-matches the unresolved names against the registry names.
Anti-fabrication rule: a fuzzy match NEVER becomes a confident pin — callers surface matches as AMBIGUOUS candidates
for the picker. Generic difflib over the registry, no vocab, no per-card logic.
"""
import difflib
import re


def _norm(s):
    return re.sub(r"[^a-z0-9]+", "", str(s).lower())


def fuzzy_rows(names, cands, cutoff=0.75, per_name=3):
    """names: the model-emitted strings that failed exact/normalized resolution. cands: asset_candidates rows.
    Returns registry rows whose name (raw or normalized) is difflib-close to any emitted name, first-seen order,
    de-duplicated. Empty list when nothing is close (caller falls through to its browse fallback)."""
    if not names or not cands:
        return []
    raw_index = {str(c[1]): c for c in cands}
    norm_index = {}
    for c in cands:
        norm_index.setdefault(_norm(c[1]), c)
    out, seen = [], set()
    for n in names:
        if not n:
            continue
        hits = difflib.get_close_matches(str(n), list(raw_index), n=per_name, cutoff=cutoff)
        hits += list(difflib.get_close_matches(_norm(n), list(norm_index), n=per_name, cutoff=cutoff))
        for h in hits:
            row = raw_index.get(h) or norm_index.get(h)
            if row is not None and row[0] not in seen:
                seen.add(row[0])
                out.append(row)
    return out
