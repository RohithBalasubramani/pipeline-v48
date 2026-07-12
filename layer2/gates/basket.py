"""layer2/gates/basket.py — the shared basket predicates every gate reads: which columns are BINDABLE (real,
data-bearing), how a failed-validation bind is worded, and whether the asset's nameplate is missing. One concern;
consumed by the walls, gate_data_instructions and gate_roster."""

def _bindable(basket):
    """(real, failed) — the columns Layer 2 may bind. The pre-L2 validation verdict is folded into the basket
    (validate/build._fold_into_basket); a validate-FAIL column (mostly-null / absent on the meter) is UNBINDABLE and
    gates exactly like a hallucinated one, carrying the validate reason so the leaf honest-blanks with a real cause
    (per-leaf degradation). A basket that never saw validation (no verdict keys) binds as before."""
    real, failed = set(), {}
    for c in (basket.get("columns") or []):
        col = c.get("column")
        if not col:
            continue
        if c.get("verdict") == "fail":
            failed[col] = "; ".join(c.get("validate_reasons") or []) or "failed pre-L2 data validation"
        else:
            real.add(col)
    return real, failed


def _col_issue(i, col, failed):
    if col in failed:
        return f"fields[{i}] column {col!r} failed pre-L2 data validation ({failed[col]}) — leaf honest-blanks"
    return f"fields[{i}] column {col!r} not in basket (hallucinated)"


def _nameplate_missing(data_instructions, basket):
    """True when the asset's nameplate rating is empty (so a nameplate:* denominator must not be used). DATA-DRIVEN
    from the basket (the caller folds nameplate availability into basket['nameplate'] when known) with a safe default:
    absent info ⇒ treat as PRESENT (do NOT blank a nameplate fn on unknown info — the executor's own fill-time
    honest-degrade still guards the divide-by-empty). Cached per call via the passed dict — no live DB in the gate."""
    npm = basket.get("nameplate")
    if isinstance(npm, dict) and "rated_present" in npm:
        return not npm.get("rated_present")
    return False
