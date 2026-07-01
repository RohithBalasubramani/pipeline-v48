"""layer3/schema.py — VALIDATE the L3 RenderSpec (names + booleans + reason ONLY, NO numbers) + PERSIST it to the
cmd_catalog.render_spec cache (reviewable / overridable rows).

The invariant this file enforces: L3 output is names/flags/reasons — it must NOT contain a rendered number, and every
name it references (bind_column, substitute_fn/column, blank_reason cause) must be a NAME that actually appears in the
fact-sheet (present column / grounded alternative) or the editable cause vocabulary. A spec that fails validation is
COERCED to an honest_blank verdict (never shipped as a fabricated render) with a machine reason.

Allowed cause keys come from config/reason_templates (cmd_catalog.reason_template) — NOT hardcoded. [contract L3 output;
audit META no-fabrication]
"""
import json

from config import reason_templates as _reasons
from data.db_client import q

_VERDICTS = {"render", "partial", "honest_blank"}
_ANSWER = {"full", "partial", "none"}
_DECISIONS = {"bind", "substitute", "blank"}
_DATE = {"enabled", "disabled"}
_NUMERIC = (int, float)


def _is_number(v):
    # booleans are NOT numbers here (they are structural flags); real int/float are forbidden in an L3 spec.
    return isinstance(v, _NUMERIC) and not isinstance(v, bool)


def _has_number_anywhere(node):
    """True if any leaf in the spec is a raw number — L3 must never emit a rendered number."""
    if isinstance(node, dict):
        return any(_has_number_anywhere(v) for v in node.values())
    if isinstance(node, (list, tuple)):
        return any(_has_number_anywhere(v) for v in node)
    return _is_number(node)


def _slot_name_set(factsheet):
    return {s.get("slot") for s in (factsheet.get("open_slots") or []) if s.get("slot")}


def _slot_by_name(factsheet, slot):
    for s in (factsheet.get("open_slots") or []):
        if s.get("slot") == slot:
            return s
    return None


def _present_columns(sf):
    cols = set()
    if sf.get("requested_column"):
        cols.add(sf["requested_column"])
    if sf.get("pre_bound_column"):
        cols.add(sf["pre_bound_column"])
    return cols


def _alt_names(sf, kind):
    return {a.get("name") for a in (sf.get("alternatives") or []) if a.get("kind") == kind and a.get("name")}


def validate_render_spec(spec, factsheet):
    """Validate + NORMALIZE the raw L3 spec against its fact-sheet. Returns (clean_spec, issues).
    On any hard violation the spec is coerced to an honest_blank with a machine reason so nothing fabricated ships."""
    issues = []
    causes = set(_reasons.all_templates().keys())
    slot_names = _slot_name_set(factsheet)

    spec = dict(spec or {})

    # --- an empty emit (Qwen fail-open) is an honest_blank, not a fabricated render -------------------------------
    if not spec:
        return _blank_spec("emit_failed", factsheet), ["emit_failed: empty L3 spec"]

    # --- HARD: no rendered number anywhere in the spec ------------------------------------------------------------
    if _has_number_anywhere(spec):
        issues.append("spec contains a raw number (L3 must emit names/booleans/reason only)")
        return _blank_spec("emit_failed", factsheet), issues

    verdict = spec.get("render_verdict")
    if verdict not in _VERDICTS:
        issues.append(f"bad render_verdict {verdict!r}")
        verdict = "honest_blank"

    answerability = spec.get("answerability")
    if answerability not in _ANSWER:
        answerability = {"render": "full", "partial": "partial", "honest_blank": "none"}.get(verdict, "none")

    date_control = spec.get("date_control")
    if date_control not in _DATE:
        date_control = "disabled"

    # --- validate each slot decision against the sheet (names must be real) ----------------------------------------
    clean_decisions = []
    for d in (spec.get("slot_decisions") or []):
        d = dict(d or {})
        slot = d.get("slot")
        sf = _slot_by_name(factsheet, slot)
        if slot not in slot_names or sf is None:
            issues.append(f"decision for unknown/hidden slot {slot!r} dropped")
            continue
        decision = d.get("decision")
        if decision not in _DECISIONS:
            issues.append(f"slot {slot}: bad decision {decision!r} -> blank")
            decision = "blank"

        bind_column = d.get("bind_column")
        sub_fn = d.get("substitute_fn")
        sub_col = d.get("substitute_column")
        blank_reason = d.get("blank_reason")

        if decision == "bind":
            if bind_column not in _present_columns(sf):
                issues.append(f"slot {slot}: bind_column {bind_column!r} not a present column -> blank")
                decision, bind_column, blank_reason = "blank", None, (blank_reason or "structurally_null")
        elif decision == "substitute":
            if sub_fn and sub_fn not in _alt_names(sf, "fn"):
                issues.append(f"slot {slot}: substitute_fn {sub_fn!r} not a grounded alternative -> blank")
                sub_fn = None
            if sub_col and sub_col not in _alt_names(sf, "column"):
                issues.append(f"slot {slot}: substitute_column {sub_col!r} not a grounded alternative -> blank")
                sub_col = None
            if not sub_fn and not sub_col:
                decision, blank_reason = "blank", (blank_reason or "structurally_null")

        if decision == "blank":
            bind_column = sub_fn = sub_col = None
            if blank_reason not in causes:
                issues.append(f"slot {slot}: blank_reason {blank_reason!r} not an allowed cause -> structurally_null")
                blank_reason = "structurally_null" if "structurally_null" in causes else (sorted(causes)[0] if causes else None)

        clean_decisions.append({
            "slot": slot, "decision": decision,
            "bind_column": bind_column, "substitute_fn": sub_fn, "substitute_column": sub_col,
            "blank_reason": blank_reason if decision == "blank" else None,
            "fidelity_note": _clean_text(d.get("fidelity_note")),
        })

    # --- suppress_default_leaves: keep only real leaf PATHS from the sheet ----------------------------------------
    valid_paths = set(factsheet.get("default_leaf_paths") or [])
    suppress = [p for p in (spec.get("suppress_default_leaves") or []) if p in valid_paths]

    # --- reason / coverage_note: text only (any stray number scrubbed already by the hard gate above) -------------
    reason = _clean_text(spec.get("reason")) or ("" if verdict == "render" else _reasons.reason("no_data"))
    coverage_note = _clean_text(spec.get("coverage_note"))

    # --- verdict self-consistency: if every slot blanked, force honest_blank -------------------------------------
    if clean_decisions and all(x["decision"] == "blank" for x in clean_decisions):
        if verdict == "render":
            verdict, answerability = "honest_blank", "none"
            issues.append("all slots blanked -> verdict coerced to honest_blank")

    clean = {
        "render_verdict": verdict,
        "reason": reason,
        "coverage_note": coverage_note,
        "answerability": answerability,
        "date_control": date_control,
        "slot_decisions": clean_decisions,
        "suppress_default_leaves": suppress,
    }
    return clean, issues


def _blank_spec(cause, factsheet):
    """A deterministic honest_blank spec (all open slots blanked with `cause`) used when the emit is unusable."""
    reason = _reasons.reason(cause, asset=(factsheet.get("asset") or {}).get("mfm_name") or "")
    decisions = [{"slot": s.get("slot"), "decision": "blank", "bind_column": None,
                  "substitute_fn": None, "substitute_column": None, "blank_reason": cause, "fidelity_note": None}
                 for s in (factsheet.get("open_slots") or [])]
    return {
        "render_verdict": "honest_blank", "reason": reason, "coverage_note": None,
        "answerability": "none", "date_control": "disabled",
        "slot_decisions": decisions, "suppress_default_leaves": list(factsheet.get("default_leaf_paths") or []),
    }


def _clean_text(v):
    if v is None:
        return None
    if isinstance(v, str):
        return v.strip() or None
    return None   # a non-string reason/note is dropped (must be a sentence, never a value)


# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#  persist — the render_spec cache (run_id, card_id, spec jsonb). Editable / overridable rows.
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
def persist_render_spec(run_id, card_id, spec):
    """Upsert the validated RenderSpec into cmd_catalog.render_spec (PK run_id, card_id). Idempotent per run."""
    payload = json.dumps(spec).replace("'", "''")
    rid = str(run_id).replace("'", "''")
    q("cmd_catalog",
      "INSERT INTO render_spec (run_id, card_id, spec) "
      f"VALUES ('{rid}', {int(card_id)}, '{payload}'::jsonb) "
      "ON CONFLICT (run_id, card_id) DO UPDATE SET spec = EXCLUDED.spec, created_at = now()")
    return True


def load_render_spec(run_id, card_id):
    """Read back a cached RenderSpec (for review / an override path), or None."""
    rows = q("cmd_catalog",
             f"SELECT spec FROM render_spec WHERE run_id='{str(run_id).replace(chr(39), chr(39)*2)}' "
             f"AND card_id={int(card_id)}")
    if not rows:
        return None
    try:
        return json.loads(rows[0][0])
    except Exception:
        return None
