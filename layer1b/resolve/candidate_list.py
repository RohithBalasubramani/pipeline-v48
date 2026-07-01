"""layer1b/resolve/candidate_list.py — shape the asset list for the frontend resolution popup. [#14, contract 3]
`for_picker` projects the AMBIGUOUS candidates; `registry_for_picker` projects the FULL registry (the popup's
empty/browse state). Both emit the identical {mfm_id,name,class,load_group,has_data} shape."""
from layer1b.resolve.asset_candidates import asset_candidates, as_asset


def for_picker(candidates):
    return [{"mfm_id": c["mfm_id"], "name": c["name"], "class": c["class"],
             "load_group": c["load_group"], "has_data": c["has_data"]} for c in candidates]


def registry_for_picker(q=None):
    """The FULL lt_mfm registry in picker shape — the resolution popup's empty/browse list. Optional substring `q`
    filters on name/class/load_group. Same projection as the ambiguous list, so both render identically."""
    rows = for_picker([as_asset(c) for c in asset_candidates()])
    if q:
        t = q.strip().lower()
        rows = [r for r in rows
                if t in f"{r['name'] or ''} {r['class'] or ''} {r['load_group'] or ''}".lower()]
    return rows
