"""layer1b/resolve/ambiguous_candidates.py — ambiguous outcome → the de-duplicated candidate list for the picker. [RN-06]

When the AI cannot pin one meter, this builds the candidate list the frontend AssetPicker shows. De-dup passes:
  1. registry-id de-dup — the AI's picks/candidates lists can name the same row twice.
  2. device-identity pass — CURRENTLY A NO-OP: confident_pin._ident returns None (the canonical device_mappings prove
     no two registry rows are the same physical device — every device has its own device_id, F5). So each row is kept as
     its own device and homonyms like DG-3 MFM vs GIC-28-N3-DG-03 [Jackson] BOTH surface for the user to disambiguate,
     instead of one being silently collapsed away. The pass is retained so a proven device_id-keyed duplication can be
     re-enabled in one place.

Order is preserved (AI/collision listing order), then STABLE-sorted data-bearing first, which the picker renders top-to-
bottom.
"""
from layer1b.resolve.asset_candidates import as_asset
from layer1b.resolve.confident_pin import _ident
from layer1b.resolve.has_data import tables_with_values


def dedup_candidates(rows, cands):
    """rows = the raw candidate registry rows (AI picks/candidates, or a class fallback); cands = the full registry.
    Returns registry rows de-duplicated by (a) registry id then (b) physical-device identity, preferring the populated
    duplicate of each device. Preserves first-seen order."""
    # (a) drop repeated registry ids
    seen_id, by_id_unique = set(), []
    for c in rows:
        if c[0] not in seen_id:
            seen_id.add(c[0])
            by_id_unique.append(c)

    # (b) collapse duplicate physical devices to their populated table
    live = tables_with_values([c[2] for c in by_id_unique if c[2]])
    seen_dev, out = set(), []
    for c in by_id_unique:
        ident = _ident(c)
        if ident is None:                                    # no duplicate pattern — keep as its own device
            out.append(c)
            continue
        if ident in seen_dev:
            continue                                         # already emitted the preferred twin for this device
        # among this device's duplicates present in the current list, prefer a populated table
        dupes = [d for d in by_id_unique if _ident(d) == ident]
        populated = [d for d in dupes if d[2] in live]
        chosen = populated[0] if populated else dupes[0]
        seen_dev.add(ident)
        out.append(chosen)
    return out


def ambiguous_candidates(rows, cands):
    """The ambiguous resolution outcome: de-dup the candidate rows and project them to asset dicts for the picker.
    STABLE-sorted data-bearing first (dead-meter-honest: the picker — and any harness auto-pick — leads with meters
    that can actually render; AI listing order is preserved within each group). [hardening: candidate ordering]
    Returns the outcome dict {asset:None, how:'ambiguous', candidates:[as_asset,...]}."""
    uniq = dedup_candidates(rows, cands)
    uniq = sorted(uniq, key=lambda c: 0 if (len(c) > 6 and c[6]) else 1)
    return {"asset": None, "how": "ambiguous", "candidates": [as_asset(c) for c in uniq]}
