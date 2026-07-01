"""layer1b/resolve/ambiguous_candidates.py — ambiguous outcome → the de-duplicated candidate list for the picker. [RN-06, DS-09]

When the AI cannot pin one meter, this builds the candidate list the frontend AssetPicker shows. Two de-dup passes so
the picker never offers junk:
  1. registry-id de-dup — the AI's picks/candidates lists can name the same row twice.
  2. device-identity prefer-populated de-dup — when a physical device has a populated table AND an empty duplicate
     (DG-01 → dg_1_mfm vs gic_28_n1_dg_01_jk), offer ONLY the populated one, so the user can't click a greyed twin
     that would blank the card. Resolution is by table membership of has_meaningful_data, never by row-id. [DS-09]

Order is preserved (AI listing order), which the picker renders top-to-bottom.
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
    Returns the outcome dict {asset:None, how:'ambiguous', candidates:[as_asset,...]}."""
    uniq = dedup_candidates(rows, cands)
    return {"asset": None, "how": "ambiguous", "candidates": [as_asset(c) for c in uniq]}
