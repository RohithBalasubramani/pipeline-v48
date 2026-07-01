"""layer1b/resolve/pinned_skip.py — PIPELINE_ASSET_ID set → skip AI resolution, pin the user's choice. [#14, RN-06]

The frontend AssetPicker round-trip: the user already chose an asset (its mfm_id comes back as PIPELINE_ASSET_ID), so
there is nothing left to resolve — pin it deterministically as how='user-choice'. Defensive: even a user-chosen asset
can be data-empty (they clicked a greyed row), so we run the same no_data gate as the AI path rather than shipping an
empty table into Layer 2. This was inlined at asset_resolve.py; extracted here as its own single-purpose, tested unit.
"""
from layer1b.resolve.asset_candidates import as_asset
from layer1b.resolve.no_data_gate import no_data_outcome


def pinned_skip(asset_id_override, by_id):
    """asset_id_override = the PIPELINE_ASSET_ID (str/int) the picker returned; by_id = {str(mfm_id): candidate_row}.
    Returns the resolved outcome dict when the id is a real registry row, else None (caller falls through to AI resolve).
      · asset has data → {asset, how:'user-choice', candidates:[]}
      · asset is empty → the NO-DATA outcome (how:'no_data') so Layer 2 is skipped and the UI names the dark asset.
    De-dup / prefer-populated is NOT applied here: the user explicitly picked THIS row, so we honor the exact pin."""
    if asset_id_override is None or str(asset_id_override) not in by_id:
        return None
    asset = as_asset(by_id[str(asset_id_override)])
    return no_data_outcome(asset) or {"asset": asset, "how": "user-choice", "candidates": []}
