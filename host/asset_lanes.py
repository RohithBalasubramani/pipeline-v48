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
        # BUS-SECTION LANE [sections]: an entry may be {"id": X, "section": "A"} — the SAME canonical panel compared
        # section-vs-section ('compare pcc 1a and pcc 1b'). The lane asset keeps the real mfm_id/table (execution is
        # identical) plus a `section` stamp (the member fan-out filter) and a sectioned display name; dedup is by
        # (id, section) so two sections of one panel are two lanes.
        section = None
        if isinstance(aid, dict):
            section = (str(aid.get("section")).strip().upper() or None) if aid.get("section") else None
            aid = aid.get("id")
        key = (str(aid), section)
        if str(aid) in by_id and key not in seen:
            seen.add(key)
            a = as_asset(by_id[str(aid)])
            if section:
                a["section"] = section
                a["name"] = f"{a.get('name')} — Section {section}"
            out.append(a)
    return out
