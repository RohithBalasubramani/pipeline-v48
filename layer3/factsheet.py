"""layer3/factsheet.py — the deterministic PRE->L3 SEAM: assemble every grounding fact into ONE self-contained
per-card FACT-SHEET in the exact shape the contract's Layer-3 I/O section mandates.

Contract (Layer 3, Input): "a self-contained fact-sheet (no raw rows, no sibling data, no rendered numbers; leaf values
stripped to placeholders; only columns/fns the kit pre-verified as present). Unambiguous slots PRE already bound are
NOT shown to L3."

So this builder:
  - reads the grounding facts already computed by the PRE kit (grounding/*.py) for this card,
  - reads the card's Layer-2 output (swap-settled exact_metadata leaf PATHS, data_instructions intent),
  - emits a fact-sheet of NAMES + BOOLEANS ONLY — every VALUE is stripped to a placeholder token,
  - lists ONLY columns/fns/assets the kit pre-verified as PRESENT (never a hallucinated or absent column),
  - splits slots into `pre_bound` (unambiguous, hidden from L3 — POST binds them straight) and `open_slots`
    (the only ones L3 sees / decides), so each L3 call is a pure function of its own sheet.

NO POLICY is hardcoded here: any threshold/name/class/reason comes from a grounding fact or a config/* accessor. This
file only RESHAPES + STRIPS. It never fetches a number. [contract PRE->L3 seam; audit META/DS/DID leaf-strip]
"""
from config import metric_class as _metric_class

# ── the placeholder token every stripped leaf value collapses to (so L3 can NEVER read a real number) ────────────────
STRIP = "<value>"


# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#  leaf-value stripping — recursively replace every scalar leaf with STRIP, keeping structure/keys/paths intact
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
def strip_values(node):
    """Recursively strip scalar leaves to the STRIP placeholder, preserving dict keys / list shape. Booleans are kept
    (they are structural flags, not rendered numbers); strings that look like metric text are stripped too so no
    fabricated literal (e.g. the DG-80% example) survives to L3. [META-01 scrub literals]"""
    if isinstance(node, dict):
        return {k: strip_values(v) for k, v in node.items()}
    if isinstance(node, (list, tuple)):
        return [strip_values(v) for v in node]
    if isinstance(node, bool) or node is None:
        return node
    # numbers + free-text strings -> stripped placeholder
    return STRIP


def _leaf_paths(node, prefix=""):
    """Every dotted leaf PATH in a payload tree (so L3 can name a suppress_default_leaves path without seeing values)."""
    out = []
    if isinstance(node, dict):
        for k, v in node.items():
            out += _leaf_paths(v, f"{prefix}.{k}" if prefix else str(k))
    elif isinstance(node, (list, tuple)):
        for i, v in enumerate(node):
            out += _leaf_paths(v, f"{prefix}[{i}]")
    else:
        out.append(prefix)
    return out


# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#  slot facts — the per-slot grounding the kit produced, reshaped to names+flags (NO numbers)
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
def _slot_fact(slot):
    """Normalize one grounding slot fact to the L3 shape. `slot` is whatever the PRE kit produced per requested metric:
        {slot, metric, requested_column, present, bind_column, substitute_fn|substitute_column,
         alternatives:[{kind:'column'|'fn', name, fidelity}], quantity, unit, blank_reason, fidelity_note}
    We keep ONLY names/flags and drop any value; we NEVER invent an alternative the kit didn't pre-verify present."""
    s = dict(slot or {})
    alts = []
    for a in (s.get("alternatives") or []):
        alts.append({"kind": a.get("kind"), "name": a.get("name"), "fidelity": a.get("fidelity")})
    return {
        "slot": s.get("slot"),
        "metric": s.get("metric"),
        "requested_column": s.get("requested_column"),
        "present": bool(s.get("present")),
        "quantity": s.get("quantity"),
        "unit": s.get("unit"),
        # PRE's pre-verified grounded bind (unambiguous) — if set, this slot is pre_bound and hidden from L3
        "pre_bound_column": s.get("bind_column"),
        # the PRE-verified grounded ALTERNATIVES L3 may choose a substitute among (names only, all pre-verified present)
        "alternatives": alts,
        "blank_reason": s.get("blank_reason"),          # machine cause key if the kit already knows the slot is blank
        "fidelity_note": s.get("fidelity_note"),
    }


def _is_unambiguous(sf):
    """A slot PRE already bound with NO competing grounded alternative → don't show it to L3 (POST binds it straight)."""
    return bool(sf.get("pre_bound_column")) and not sf.get("alternatives")


# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#  the builder — assemble the whole fact-sheet from the grounding kit output + the L2 card output
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
def build_factsheet(*, run_id, card_id, grounding, l2_out, page_key):
    """Assemble the self-contained per-card fact-sheet.

    Inputs (all already computed upstream — this file only reshapes+strips):
      grounding : the PRE grounding kit's per-card fact bag (dict) — see the keys read below. Missing keys degrade to
                  honest defaults so the sheet is always well-formed even while the kit is partial.
      l2_out    : the settled Layer2CardOutput (swap already resolved deterministically before L3) — we read the
                  exact_metadata leaf PATHS (values stripped) + the data_instructions intent + the default-payload paths.
      page_key  : the routed page (drives required metric classes via config/metric_class — NO hardcoded map).

    Output: the fact-sheet dict (names/booleans/placeholders only) consumed by prompt.py. Also returns `pre_bound`
    (the slots hidden from L3, bound straight in POST) so the seam is explicit.
    """
    g = grounding or {}
    l2 = l2_out or {}

    asset = g.get("asset") or {}
    fingerprint = g.get("schema_fingerprint")
    required_classes = _metric_class.required_classes(page_key)   # config-driven page->class

    # --- per-slot facts: split into pre_bound (hidden) vs open_slots (shown to L3) -----------------------------------
    slot_facts = [_slot_fact(s) for s in (g.get("slot_facts") or [])]
    pre_bound = [sf for sf in slot_facts if _is_unambiguous(sf)]
    open_slots = [sf for sf in slot_facts if not _is_unambiguous(sf)]

    # --- the default-payload leaf PATHS (so L3 can name suppress_default_leaves without seeing any value) ------------
    default_payload = l2.get("_default_payload")
    default_leaf_paths = _leaf_paths(default_payload) if default_payload else []

    # --- exact_metadata: keep ONLY the structure/keys, strip every leaf value to STRIP -------------------------------
    exact_metadata_shape = strip_values(l2.get("exact_metadata") or {})

    # --- data_instructions intent (which metrics/endpoint/window the STORY wants) — names only, no values -----------
    di = l2.get("data_instructions") or {}
    consumer = di.get("consumer") or {}
    data_intent = {
        "fields": [{"metric": f.get("metric"), "column": f.get("column"), "kind": f.get("kind"),
                    "fn": f.get("fn"), "unit": f.get("unit")}
                   for f in (di.get("fields") or [])],
        "payload_shape": di.get("payload_shape"),
        "orientation": di.get("orientation"),
    }

    sheet = {
        "run_id": run_id,
        "card_id": card_id,
        "page_key": page_key,
        "story": {
            "render_slot": l2.get("render_slot"),
            "analytical_story": l2.get("analytical_story"),
        },
        # ── ASSET IDENTITY (names/flags; no rows) ────────────────────────────────────────────────────────────────
        "asset": {
            "mfm_id": asset.get("mfm_id"),
            "asset_table": asset.get("asset_table") or asset.get("table"),
            "mfm_name": asset.get("mfm_name") or asset.get("name"),
            "asset_category": asset.get("asset_category"),
            "role": asset.get("role"),
            "section": asset.get("section"),
            "resolver_scope": asset.get("resolver_scope") or g.get("resolver_scope"),
            "preferred_populated_dup": asset.get("preferred_populated_dup"),   # DS-09 de-dup outcome (flag)
        },
        # ── SCHEMA / METRIC-CLASS FEASIBILITY (booleans only) ────────────────────────────────────────────────────
        "schema": {
            "fingerprint": fingerprint,
            "required_classes": required_classes,
            "class_present": g.get("class_present"),        # {class: bool} — does the table expose the page's class
            "meaningful": bool(g.get("meaningful")),         # the ONE shared has_meaningful_data verdict (flag)
            "meaningful_reason": g.get("meaningful_reason"),  # machine cause key if not meaningful
        },
        # ── NAMEPLATE PRESENCE (flags only; the actual numbers stay in POST) ─────────────────────────────────────
        "nameplate": {
            "has_rated": g.get("has_rated"),
            "has_contracted": g.get("has_contracted"),
            "has_nominal_voltage": g.get("has_nominal_voltage"),
            "source": g.get("nameplate_source"),
        },
        # ── DATA-QUALITY FLAGS the kit already determined (all booleans / cause keys, no numbers) ─────────────────
        "quality": {
            "table_has_rows": g.get("table_has_rows"),
            "reversed_ct": g.get("reversed_ct"),             # DS-05: import~0 & export>0 -> export register (flag)
            "denorm_garbage": g.get("denorm_garbage"),        # DS-06 flag
            "structurally_null_metrics": g.get("structurally_null_metrics") or [],  # names only (DS-04)
            "window_since_available": bool(g.get("window_since")),  # DS-02 flag (the DATE stays out of L3)
        },
        # ── TOPOLOGY / AGGREGATE COVERAGE (counts are structural, not rendered numbers → kept as counts) ──────────
        "topology": {
            "is_aggregate": g.get("is_aggregate"),
            "members_total": g.get("members_total"),          # M in "N of M feeders"
            "members_reporting": g.get("members_reporting"),  # N (structural coverage, drives coverage_note)
            "incomer_verified": g.get("incomer_verified"),    # TOPO-02 flag
            "has_topology": g.get("has_topology"),            # TOPO-01 flag
        },
        # ── ENDPOINT / SHAPE (names/flags) ───────────────────────────────────────────────────────────────────────
        "endpoint": {
            "endpoint": g.get("endpoint") or consumer.get("endpoint"),
            "expected_shape": g.get("expected_shape"),
            "is_history": g.get("is_history"),
            "endpoint_live": g.get("endpoint_live"),          # ER-8: pre-validated vs the LIVE endpoint set (flag)
            "date_navigable": g.get("date_navigable"),        # ER-7: does the domain HAVE a history variant (flag)
        },
        # ── SLOTS shown to L3 (open) + those hidden (pre_bound) ───────────────────────────────────────────────────
        "open_slots": open_slots,
        "pre_bound_count": len(pre_bound),
        # ── PAYLOAD SHAPE (leaf PATHS only; every value stripped) ─────────────────────────────────────────────────
        "exact_metadata_shape": exact_metadata_shape,
        "default_leaf_paths": default_leaf_paths,
        "data_intent": data_intent,
        # ── ANSWERABILITY first-guess from L2 (a HINT; L3 re-decides against ground truth) ───────────────────────
        "l2_answerability": l2.get("answerability"),
        "l2_gap": bool(l2.get("gap")),
    }
    return {"factsheet": sheet, "pre_bound": pre_bound}
