"""host/asset_lanes.py — resolve the picker's asset_ids to the canonical asset dicts a multi-asset compare consumes.
[multi-asset] AI-free: a straight registry lookup (asset_candidates → as_asset) keyed by the mfm_id the picker returned
(the SAME id-space pinned_skip uses). Unknown ids are DROPPED (honest — a stale id never fabricates an asset). Order
preserved, duplicates collapsed. Single concern; host/multi_asset drives run_pipeline_multi through this.
"""
from layer1b.resolve.asset_candidates import asset_candidates, as_asset


def resolve_assets(asset_ids):
    """[as_asset dict, …] for the given mfm_ids — order preserved, unknown ids skipped, duplicates kept once. Each dict
    carries name / table / class / mfm_id / has_data — enough to group by class, fill from its table, and tag the card."""
    by_id = {str(c[0]): c for c in asset_candidates()}
    out, seen = [], set()
    for aid in (asset_ids or []):
        key = str(aid)
        if key in by_id and key not in seen:
            seen.add(key)
            out.append(as_asset(by_id[key]))
    return out
