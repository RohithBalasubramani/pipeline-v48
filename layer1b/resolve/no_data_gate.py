"""layer1b/resolve/no_data_gate.py — the NO-DATA resolution outcome (the extra resolution layer). The user named an
asset that EXISTS in the registry but whose neuract data table is EMPTY (never-wired / not-yet-logging). This is
DISTINCT from the other 1b outcomes:
  · how='AI'/'user-choice' — resolved AND has data  -> run Layer 2, render the cards
  · how='ambiguous'        — several candidates      -> the picker, choose one
  · how='empty'            — NO asset named          -> pure metric prompt
  · how='no_data'  (THIS)  — resolved the asset, it just has no rows yet -> the frontend shows a 'no data for <asset>'
                             notice. Keeps the asset (name/class) so the UI can say WHICH asset is dark.

NOT-A-DEAD-END [hardening — batch 1/2 UX defect]: a no_data outcome used to carry candidates=[] , which opened the
AssetResolution picker with the named asset greyed and ZERO alternatives — a terminal with no path forward. The picker
is a resolution surface: it must always offer SOMETHING to pick. So no_data now carries an ALTERNATIVES list (same-class
data-bearing meters first, then plant-wide data-bearing), de-duplicated by device identity + prefer-populated, exactly
like the ambiguous list. The named-dark asset still rides in `asset`/`no_data_asset` so the FE greys it; the candidates
give the user a real onward pick. Generic — no per-asset ids/vocab; alternatives come straight from the live registry.
"""
from layer1b.resolve.ambiguous_candidates import dedup_candidates
from layer1b.resolve.asset_candidates import as_asset


def _alternatives(asset, cands):
    """The onward-pick list for a NO-DATA asset: DATA-bearing registry rows, SAME class first (the user asked about a
    panel → offer other panels), then plant-wide, de-duplicated by device identity (prefer-populated) and never
    including the dark asset itself. Empty only if the whole plant is dark (degenerate). Order: same-class-with-data,
    then other-class-with-data; dedup_candidates preserves first-seen order + collapses twin duplicates."""
    dark_id = str(asset.get("mfm_id")) if asset else None
    live = [c for c in cands if len(c) > 6 and c[6] and str(c[0]) != dark_id]   # data-bearing, not the dark asset
    cls = asset.get("class") if asset else None
    same_cls = [c for c in live if c[5] == cls]
    other = [c for c in live if c[5] != cls]
    ordered = same_cls + other
    if not ordered:
        return []
    uniq = dedup_candidates(ordered, cands)
    return [as_asset(c) for c in uniq]


def no_data_outcome(asset, cands=None):
    """asset = a resolved asset dict (as_asset). Returns the NO-DATA resolution when the asset has no data, else None.
    When `cands` (the full registry rows) is supplied, the outcome carries onward-pick ALTERNATIVES so the picker is
    never a dead end (the named-dark asset stays in `asset` so the FE can grey it)."""
    if asset and not asset.get("has_data"):
        return {"asset": asset, "how": "no_data",
                "candidates": _alternatives(asset, cands) if cands else []}
    return None
