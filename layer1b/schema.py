"""layer1b/schema.py — assemble + validate Layer1bOutput. [contract 3]"""
from layer1b.resolve.candidate_list import for_picker


def build_layer1b_output(resolved, basket):
    return {
        "asset": resolved.get("asset"),
        "how": resolved.get("how"),
        "candidate_list": for_picker(resolved.get("candidates", [])),
        "column_basket": basket,
    }


def validate_layer1b_output(out):
    p = []
    how = out.get("how")
    if how not in {"AI", "user-choice", "ambiguous", "empty", "no_data"}:
        p.append(f"bad how: {how!r}")
    if how == "ambiguous" and not out.get("candidate_list"):
        p.append("ambiguous but no candidate_list")
    if how == "no_data" and not out.get("asset"):
        p.append("no_data but no asset (must name which asset is dark)")
    if how in {"AI", "user-choice"}:                                  # the RESOLVED-WITH-DATA states (no_data is excluded)
        if not out.get("asset"):
            p.append(f"how={how} but no asset")
        elif not out.get("column_basket", {}).get("columns"):
            p.append("resolved asset but empty column_basket")
    return p
