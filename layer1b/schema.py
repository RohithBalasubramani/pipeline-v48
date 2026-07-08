"""layer1b/schema.py — assemble + validate Layer1bOutput. [contract 3]"""
from layer1b.resolve.candidate_list import for_picker


def build_layer1b_output(resolved, basket):
    return {
        "asset": resolved.get("asset"),
        "how": resolved.get("how"),
        "candidate_list": for_picker(resolved.get("candidates", [])),
        "column_basket": basket,
        # resolution telemetry (NOT gates): the prompt-implied class prior, whether the resolution disagrees with it,
        # and whether the resolver LLM was never heard (fail-open {} twice). [hardening: class-consistency telemetry]
        "class_prior": resolved.get("class_prior"),
        "class_mismatch": bool(resolved.get("class_mismatch")),
        "llm_failed": bool(resolved.get("llm_failed")),
    }


def validate_layer1b_output(out):
    p = []
    how = out.get("how")
    # collision_gate_fullname = the deterministic full-name pin (attributable to the collision gate, not the model) — a
    # legitimate RESOLVED-WITH-DATA state; treated as a confident pin below (basket + no-picker safety checks apply).
    if how not in {"AI", "user-choice", "ambiguous", "empty", "no_data", "collision_gate_fullname"}:
        p.append(f"bad how: {how!r}")
    if how == "ambiguous" and not out.get("candidate_list"):
        p.append("ambiguous but no candidate_list")
    if how == "no_data" and not out.get("asset"):
        p.append("no_data but no asset (must name which asset is dark)")
    if how in {"AI", "user-choice", "collision_gate_fullname"}:       # the RESOLVED-WITH-DATA states (no_data is excluded)
        if not out.get("asset"):
            p.append(f"how={how} but no asset")
        elif not out.get("column_basket", {}).get("columns"):
            p.append("resolved asset but empty column_basket")
    if (out.get("column_basket") or {}).get("llm_failed"):            # basket AI never heard — floor-only basket [item 15]
        p.append("basket llm_failed (fail-open {} twice) — basket is the logged floor only")
    return p
