"""layer2/gates/roster.py — gate_roster: recipe-authoritative roster validation/normalization."""
from layer2.gates.basket import _bindable

def gate_roster(roster, roster_spec, basket):
    """Validate + normalize data_instructions.roster against the card's card_fill_recipe row. [package §2d]

    Returns (ok, issues, normalized_roster). The recipe row is AUTHORITATIVE — the AI's ONLY authority is the COLUMN
    inside a col/delta/phase_mean/prefer_abs binding (each named column must exist VERBATIM in the basket); slot paths,
    element keys, role_filter/group_by/order/caps and reducers/floors are FIXED by the recipe. VALIDATION, not
    correction: a non-conforming part is reported (telemetry) and the recipe truth ships in its place; a clean column
    choice is folded in. Recipe slots the AI omitted are appended verbatim (deterministic fail-open, META-08 pattern),
    so an AI that emits no roster still ships the full recipe-derived roster — per-leaf degradation, never a blank card."""
    real, _failed = _bindable(basket)          # validate-FAIL columns are unbindable here too (pre-L2 verdict)
    spec_slots = {s.get("slot"): s for s in (roster_spec or {}).get("slots") or [] if isinstance(s, dict)}
    issues, normalized = [], []
    if roster and not spec_slots:
        return False, ["roster emitted for a card with no roster recipe"], []
    for i, r in enumerate(roster or []):
        if not isinstance(r, dict):
            issues.append(f"roster[{i}] is not an object"); continue
        s = spec_slots.get(r.get("slot"))
        if s is None:
            issues.append(f"roster[{i}] slot {r.get('slot')!r} not in card recipe"); continue
        if r.get("scope") not in (None, "members"):
            issues.append(f"roster[{i}] bad scope {r.get('scope')!r}")
        for k in ("role_filter", "group_by", "order"):
            if r.get(k) not in (None, s.get(k)):
                issues.append(f"roster[{i}] {k}={r.get(k)!r} != recipe {s.get(k)!r}")
        if r.get("cap") is not None and s.get("cap") is not None and r["cap"] > s["cap"]:
            issues.append(f"roster[{i}] cap {r['cap']} > recipe cap {s['cap']}")
        # element: keys ⊆ recipe keys; a recipe honest-null key STAYS null; every named column ∈ basket (verbatim-real)
        merged = {k: (dict(v) if isinstance(v, dict) else v) for k, v in (s.get("element") or {}).items()}
        for k, v in (r.get("element") or {}).items():
            if k not in merged:
                issues.append(f"roster[{i}].element key {k!r} not in recipe (invented)"); continue
            b = {"b": "col", "c": v} if isinstance(v, str) else (v if isinstance(v, dict) else {})
            spec_b = merged[k] if isinstance(merged[k], dict) else {}
            if spec_b.get("b") == "null" and b.get("b") != "null":
                issues.append(f"roster[{i}].element {k!r} is honest-null in recipe; column binding rejected"); continue
            if b.get("c") == spec_b.get("c") and list(b.get("cs") or []) == list(spec_b.get("cs") or []):
                continue                                # verbatim repeat of the recipe's own binding = recipe truth
                # (member-scope columns live on MEMBER tables — the panel's own basket may not carry them; only a
                #  column the AI CHANGED is its decision, and THAT must be a real basket column below)
            bad = [c for c in ([b.get("c")] if b.get("c") else []) + list(b.get("cs") or []) if c not in real]
            if bad:
                issues += [f"roster[{i}].element {k!r} column {c!r} not in basket (hallucinated)" for c in bad]
                continue
            merged[k] = {**spec_b, **{kk: b[kk] for kk in ("c", "cs") if kk in b}}   # clean column choice folds in
        # reducers/floors are FIXED by the recipe — the AI may not move thresholds or invent aggregations
        for agg_key in ("agg", "group_agg", "section_agg"):
            _r_agg = r.get(agg_key)
            if not isinstance(_r_agg, dict):
                continue                                       # a string/list agg emission is normalized from the recipe, never indexed
            for k in _r_agg:
                if (s.get(agg_key) or {}).get(k) != _r_agg[k]:
                    issues.append(f"roster[{i}].{agg_key}[{k!r}] differs from recipe (thresholds/reducers are fixed)")
        norm = dict(s)                                          # recipe wins wholesale …
        if "element" in s:
            norm["element"] = merged                            # … with the AI's validated columns folded in
        normalized.append(norm)
    # backfill: recipe slots the AI omitted ship VERBATIM (deterministic fail-open — full roster even on emit failure)
    emitted = {r.get("slot") for r in (roster or []) if isinstance(r, dict)}
    normalized += [dict(s) for slot, s in spec_slots.items() if slot not in emitted]
    return (not issues), issues, normalized
