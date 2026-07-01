"""layer3/apply.py — POST (deterministic; NO AI): take the validated RenderSpec + the resolved asset, FETCH the real
number for every bind/substitute slot, RANGE/SIGN-VERIFY it, FORCE-BLANK the suppress_default_leaves, and thread the
reason / coverage / fidelity channel onto the card envelope.

Contract POST: "Value fetch + range/sign verify for every L3 bind/substitute (registry.run); probe violation ->
blank+reason." + "force-blank suppress_default_leaves + watermark" + "reason channel: thread per-slot blank_reason /
coverage_note / fidelity_note".

EVERY policy is read from a config/* accessor — value_min, denorm_epsilon, reversed_ct_import_max, negative-power
convention, coverage-partial %, and every reason SENTENCE. ZERO magic numbers / mappings live in this file. The AI
already NAMED the column/fn; this file only FETCHES + VERIFIES + assembles. [audit DS-05/06, VC-01/02/03, ER-6]
"""
from config import quality_policy as _qp
from config import reason_templates as _reasons
from config import derivation_binding as _deriv
from config import nameplates as _np
from data.db_client import q
from ems_backend.lt_panels.derivations import registry as _registry

# machine-cause keys used here (the SENTENCES live in cmd_catalog.reason_template — only the KEYS are referenced)
_C_DENORM = "denorm_garbage"
_C_REVERSED = "reversed_ct"
_C_STRUCT = "structurally_null"
_C_NODATA = "no_data"
_C_NONAMEPLATE = "no_nameplate"
_C_EMPTY_FEEDERS = "empty_feeders"


# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#  deterministic live fetch — latest row / windowed rows for the resolved asset (NO fabrication)
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
def _esc(s):
    return str(s).replace("'", "''")


def _latest_row(asset_table, columns):
    """The latest row's {column: value} for the given present columns (or {} if the table is empty). Deterministic
    read of the live DATA db; only columns the sheet marked present are ever requested (no missing-column crash)."""
    cols = [c for c in (columns or []) if c]
    if not asset_table or not cols:
        return {}
    from config.databases import DATA_DB, DATA_SCHEMA, DATA_TS_COL, DATA_TS_CAST
    sel = ", ".join(f'"{_esc(c)}"' for c in cols)
    sql = (f'SELECT {sel} FROM {DATA_SCHEMA}."{_esc(asset_table)}" '
           f'ORDER BY "{DATA_TS_COL}"{DATA_TS_CAST} DESC LIMIT 1')
    try:
        rows = q(DATA_DB, sql)
    except Exception:
        return {}
    if not rows:
        return {}
    return {c: _num(v) for c, v in zip(cols, rows[0])}


def _num(x):
    if x in (None, "", "NULL"):
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return x   # keep non-numeric text as-is (rare; e.g. ups_mode)


# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#  range / sign verification — every gate value comes from config/quality_policy (NO magic numbers)
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
def verify_value(value, *, quantity=None):
    """Range/sign-verify a fetched number against the editable quality policy. Returns (clean_value, fidelity_note,
    blank_cause). blank_cause is set (and clean_value None) ONLY on a hard violation → the slot honest-blanks.

      - denormalized-float garbage |x| < denorm_epsilon  -> treat as no reading (DS-06) -> blank denorm_garbage
      - genuine negative power under the configured convention -> abs() + a leading/lagging note (DS-06/VC-03)
    """
    if value is None:
        return None, None, _C_STRUCT
    if not isinstance(value, (int, float)):
        return value, None, None   # non-numeric text passes through (no range concept)

    eps = _qp.num("denorm_epsilon", 1e-30)
    if value != 0 and abs(value) < eps:
        return None, None, _C_DENORM

    note = None
    if value < 0 and quantity in ("power", "energy"):
        conv = _qp.txt("negative_power_convention", "abs_with_flag")
        if conv == "abs_with_flag":
            note = "reverse power flow"
            value = abs(value)
    return value, note, None


# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#  substitute execution — run the named recovery fn via registry.run (the AI NAMED it; we EXECUTE + verify)
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
def _window_rows(asset_table, columns):
    """(start_row, end_row) over the meter's FULL logged window for the given cumulative columns — the earliest and
    latest rows. Windowed-delta fns (windowEnergyKwh/todaysEnergyTotalKwh/…) read start_row/end_row. Deterministic;
    only present columns are requested. Empty table -> ({}, {})."""
    cols = [c for c in (columns or []) if c]
    if not asset_table or not cols:
        return {}, {}
    from config.databases import DATA_DB, DATA_SCHEMA, DATA_TS_COL, DATA_TS_CAST
    sel = ", ".join(f'"{_esc(c)}"' for c in cols)
    tbl = f'{DATA_SCHEMA}."{_esc(asset_table)}"'
    try:
        first = q(DATA_DB, f'SELECT {sel} FROM {tbl} ORDER BY "{DATA_TS_COL}"{DATA_TS_CAST} ASC LIMIT 1')
        last = q(DATA_DB, f'SELECT {sel} FROM {tbl} ORDER BY "{DATA_TS_COL}"{DATA_TS_CAST} DESC LIMIT 1')
    except Exception:
        return {}, {}
    s = {c: _num(v) for c, v in zip(cols, first[0])} if first else {}
    e = {c: _num(v) for c, v in zip(cols, last[0])} if last else {}
    return s, e


def _run_substitute_fn(fn, asset_table, nameplate_scope):
    """Execute a NAMED library fn deterministically. Builds a SUPERSET ctx from live data — the latest row, the
    windowed (start_row,end_row) over the meter's logged range, AND nameplate:* pseudo-cols from asset_nameplate — so
    ANY class of fn (instantaneous / windowed-delta / nameplate-from-name) computes without this file hardcoding which
    ctx each fn needs (every derivation fn null-guards and reads only its own keys). Returns (value, fidelity) or
    (None, None) on honest-degrade (missing inputs / unknown fn). NEVER fabricates."""
    binding = _deriv.binding(fn)
    fidelity = binding["fidelity"] if binding else None
    base = binding["base_columns"] if binding else []
    frame_cols = [c for c in base if not c.startswith("nameplate:")]

    row = _latest_row(asset_table, frame_cols) if frame_cols else {}
    start_row, end_row = _window_rows(asset_table, frame_cols) if frame_cols else ({}, {})

    # nameplate:* pseudo-cols come from the asset_nameplate table (config/nameplates), NOT the frame
    if any(c.startswith("nameplate:") for c in base):
        np = _np.get_nameplate(nameplate_scope or asset_table) or {}
        got_rated = False
        for c in base:
            if c.startswith("nameplate:"):
                key = c.split(":", 1)[1]
                v = np.get(key)
                row[c] = v
                if key == "rated_kva":
                    got_rated = v is not None
        # a rated-kva-denominator fn with no nameplate -> honest-degrade (never assume a rating)
        if "nameplate:rated_kva" in base and not got_rated:
            return None, None

    # the derivation fns null-guard missing inputs -> None (never fabricate). Superset ctx keeps this file fn-agnostic.
    val = _registry.run(fn, {"row": row, "start_row": start_row, "end_row": end_row, "name": nameplate_scope})
    return val, fidelity


# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#  suppress_default_leaves — force-blank a dotted/indexed payload path so no seed value leaks as live [VC-01/02]
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
def _set_path(tree, path, value):
    """Set a dotted/indexed leaf path (a.b[0].c) to `value` in-place; silently no-ops if the path doesn't resolve."""
    import re
    toks = re.findall(r"[^.\[\]]+", path or "")
    if not toks:
        return
    node = tree
    for t in toks[:-1]:
        key = int(t) if t.isdigit() else t
        try:
            node = node[key]
        except (KeyError, IndexError, TypeError):
            return
    last = toks[-1]
    key = int(last) if last.isdigit() else last
    try:
        node[key] = value
    except (KeyError, IndexError, TypeError):
        return


def suppress_leaves(payload, paths):
    """Force every listed leaf path in `payload` to None (honest blank), returning the count actually blanked. The
    frontend reads None as 'no live value' — never a seed number shown as live. [NO-SEED-LEAK systemic fix]"""
    if not payload or not paths:
        return 0
    n = 0
    for p in paths:
        _set_path(payload, p, None)
        n += 1
    return n


# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#  the POST assembler — apply the RenderSpec onto the card, fetch+verify each slot, thread the reason channel
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
def apply_render_spec(*, spec, factsheet, exact_metadata=None):
    """POST: turn the validated RenderSpec into a rendered envelope.

    Returns an envelope dict:
      { render_verdict, reason, coverage_note, answerability, date_control,
        slots: {slot: {value|None, fidelity_note, blank_reason, source}},
        suppressed_leaf_count, watermark, exact_metadata (with suppressed leaves force-blanked) }

    Every value here is FETCHED live + VERIFIED; a probe violation blanks the slot with a machine reason. No number is
    ever invented; a missing input honest-blanks. [contract POST]
    """
    asset = (factsheet or {}).get("asset") or {}
    asset_table = asset.get("asset_table")
    nameplate_scope = asset.get("asset_table")
    quantity_by_slot = {s.get("slot"): s.get("quantity") for s in (factsheet.get("open_slots") or [])}

    slots_out = {}
    any_real = False
    all_blank = True

    for d in (spec.get("slot_decisions") or []):
        slot = d.get("slot")
        decision = d.get("decision")
        qy = quantity_by_slot.get(slot)

        if decision == "bind":
            col = d.get("bind_column")
            row = _latest_row(asset_table, [col]) if col else {}
            raw = row.get(col)
            val, vnote, cause = verify_value(raw, quantity=qy)
            if cause:
                slots_out[slot] = _blank_slot(cause, asset)
            else:
                slots_out[slot] = {"value": val, "fidelity_note": _join_notes(d.get("fidelity_note"), vnote),
                                   "blank_reason": None, "source": {"kind": "column", "name": col}}
                any_real = any_real or (val is not None)
                all_blank = all_blank and (val is None)

        elif decision == "substitute":
            fn = d.get("substitute_fn")
            sub_col = d.get("substitute_column")
            if fn:
                raw, fid = _run_substitute_fn(fn, asset_table, nameplate_scope)
                val, vnote, cause = verify_value(raw, quantity=qy)
                if cause or val is None:
                    slots_out[slot] = _blank_slot(cause or _C_STRUCT, asset)
                else:
                    note = _join_notes(d.get("fidelity_note"), vnote, _fidelity_word(fid))
                    slots_out[slot] = {"value": val, "fidelity_note": note, "blank_reason": None,
                                       "source": {"kind": "fn", "name": fn, "fidelity": fid}}
                    any_real = True
                    all_blank = False
            elif sub_col:
                row = _latest_row(asset_table, [sub_col])
                raw = row.get(sub_col)
                val, vnote, cause = verify_value(raw, quantity=qy)
                if cause:
                    slots_out[slot] = _blank_slot(cause, asset)
                else:
                    note = _join_notes(d.get("fidelity_note"), vnote, "substituted column")
                    slots_out[slot] = {"value": val, "fidelity_note": note, "blank_reason": None,
                                       "source": {"kind": "column", "name": sub_col}}
                    any_real = any_real or (val is not None)
                    all_blank = all_blank and (val is None)
            else:
                slots_out[slot] = _blank_slot(_C_STRUCT, asset)

        else:  # blank
            slots_out[slot] = _blank_slot(d.get("blank_reason") or _C_STRUCT, asset)

    # ── force-blank the seed-leaking default leaves the AI named ─────────────────────────────────────────────────
    em = exact_metadata if exact_metadata is not None else (factsheet.get("exact_metadata_shape") or {})
    suppressed = suppress_leaves(em, spec.get("suppress_default_leaves") or [])

    # ── coverage note for an aggregate (structural counts from the sheet; the SENTENCE from config) ──────────────
    coverage_note = spec.get("coverage_note")
    topo = (factsheet or {}).get("topology") or {}
    if not coverage_note and topo.get("is_aggregate") and topo.get("members_total") is not None:
        rep, tot = topo.get("members_reporting"), topo.get("members_total")
        if rep is not None and tot is not None and rep < tot:
            coverage_note = _reasons.reason(_C_EMPTY_FEEDERS, reporting=rep, expected=tot)

    # ── final verdict reconciliation against the ACTUAL fetched result (deterministic override of a stale verdict) ─
    verdict = spec.get("render_verdict") or "honest_blank"
    if slots_out:
        if all_blank:
            verdict, answerability = "honest_blank", "none"
        elif not any_real or _any_blank(slots_out):
            verdict = "partial" if any_real else "honest_blank"
            answerability = "partial" if any_real else "none"
        else:
            verdict, answerability = "render", "full"
    else:
        answerability = spec.get("answerability") or ("full" if verdict == "render" else "none")

    reason = spec.get("reason")
    if verdict != "render" and not reason:
        reason = _reasons.reason(_C_NODATA, asset=asset.get("mfm_name") or asset_table or "")

    return {
        "render_verdict": verdict,
        "answerability": answerability,
        "reason": reason,
        "coverage_note": coverage_note,
        "date_control": spec.get("date_control") or "disabled",
        "slots": slots_out,
        "exact_metadata": em,                          # already force-blanked at suppress_default_leaves (NO-SEED-LEAK)
        "suppress_default_leaves": spec.get("suppress_default_leaves") or [],  # the paths (for the FE watermark/transparency)
        "suppressed_leaf_count": suppressed,
        "watermark": "live",              # provenance stamp; a suppressed/blank slot carries None, never a seed number
    }


def _blank_slot(cause, asset):
    return {"value": None, "fidelity_note": None, "blank_reason": cause,
            "source": {"kind": "blank"},
            "reason": _reasons.reason(cause, asset=(asset or {}).get("mfm_name") or "",
                                      metric="", required_class="", device_kind="")}


def _any_blank(slots_out):
    return any(v.get("value") is None for v in slots_out.values())


def _join_notes(*notes):
    parts = [n for n in notes if n]
    return "; ".join(parts) if parts else None


def _fidelity_word(fid):
    return None if not fid or fid == "real_exact" else f"fidelity: {fid}"
