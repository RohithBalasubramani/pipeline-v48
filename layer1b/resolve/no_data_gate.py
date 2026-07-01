"""layer1b/resolve/no_data_gate.py — the NO-DATA resolution outcome (the extra resolution layer). The user named an
asset that EXISTS in the registry but whose neuract data table is EMPTY (never-wired / not-yet-logging). This is
DISTINCT from the other 1b outcomes:
  · how='AI'/'user-choice' — resolved AND has data  -> run Layer 2, render the cards
  · how='ambiguous'        — several candidates      -> the picker, choose one
  · how='empty'            — NO asset named          -> pure metric prompt
  · how='no_data'  (THIS)  — resolved the asset, it just has no rows yet -> SKIP Layer 2 (nothing to fill); the
                             frontend shows a 'no data for <asset>' notice (the picker's terminal/no-data state).
Keeps the asset (name/class) so the UI can say WHICH asset is dark, instead of a generic 'not found'."""


def no_data_outcome(asset):
    """asset = a resolved asset dict (as_asset). Returns the NO-DATA resolution when the asset has no data, else None."""
    if asset and not asset.get("has_data"):
        return {"asset": asset, "how": "no_data", "candidates": []}
    return None
