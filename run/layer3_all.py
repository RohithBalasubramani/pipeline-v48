"""run/layer3_all.py — the PRE->L3->POST fan-out (mirrors run/layer2_all.py). The 3rd/last AI layer of the pipeline.

For EVERY settled Layer-2 card this file:
  1. PRE  (deterministic, NO AI) — assemble the card's per-card GROUNDING BAG by orchestrating the grounding/* engines
     against the live neuract DB + the cmd_catalog config tables (meaningful / nameplate / metric-class / schema-
     fingerprint / energy-register / endpoint+shape / aggregate-coverage). ZERO policy is hardcoded here — every
     threshold/name/class/reason comes from a grounding fact or a config/* accessor.
  2. L3   (the ONE AI call, parallel per card) — layer3.factsheet.build_factsheet -> layer3.emit.emit_render_spec ->
     layer3.schema.validate_render_spec (names+booleans+reason ONLY; a fail-open {} honest-degrades to a blank spec).
  3. POST (deterministic, NO AI) — layer3.apply.apply_render_spec: FETCH+range/sign-VERIFY every bound/substitute slot,
     force-blank the suppress_default_leaves, thread the reason/coverage/fidelity channel onto the card envelope.

The swap collision between slots is already settled DETERMINISTICALLY before this file runs (run/layer2_all.py post-pass
+ grounding.swap_settle), so each L3 call is a pure function of its own fact-sheet → the within-layer calls stay
independent → the 3-AI-layer contract holds. Per-card exceptions are captured (one bad card never sinks the page).
[contract PRE->L3->POST seam]
"""
from run.parallel import run_parallel
from obs.stage import stage

# grounding engines (deterministic PRE) + the L3 pieces (factsheet/emit/schema/apply)
from grounding import meaningful as _meaningful
from grounding import metric_class as _metric_class
from grounding import nameplate as _np
from grounding import schema_fingerprint as _fp
from grounding import schema_route as _route
from grounding import energy_register as _energy
from grounding import endpoint_resolve as _endpoint
from grounding import aggregate as _aggregate
from grounding import window_clamp as _window
from grounding import recovery_validate as _recovery
from layer3.factsheet import build_factsheet
from layer3.emit import emit_render_spec
from layer3.schema import validate_render_spec, persist_render_spec
from layer3.apply import apply_render_spec


# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#  PRE — build the per-card GROUNDING BAG (deterministic; the exact key shape factsheet.build_factsheet reads)
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
def _asset_table(asset):
    a = asset or {}
    return a.get("table") or a.get("table_name") or a.get("asset_table")


def _slot_facts(asset_table, di, page_key):
    """Build the per-slot grounding facts for the fact-sheet from the card's data_instructions.fields[] intent + the
    table's routed schema map. A slot is PRE-BOUND (hidden from L3) iff its requested metric maps to exactly one present
    column; otherwise it is an OPEN slot with the grounded alternatives L3 may substitute among. NO number is fetched
    here — names/flags only. Absent columns honest-degrade to a blank_reason (never hallucinated)."""
    if not asset_table:
        return []
    routed = _route.routed_map(asset_table)                      # {slot: {column_name, unit, quantity}}
    present_cols = {m.get("column_name") for m in routed.values() if m.get("column_name")}
    by_quantity = {}
    for m in routed.values():
        by_quantity.setdefault(m.get("quantity"), []).append(m)

    facts = []
    for i, f in enumerate(di.get("fields") or []):
        if not isinstance(f, dict):
            continue
        metric = f.get("metric")
        req_col = f.get("column")
        quantity = f.get("unit") and _quantity_of(f) or _quantity_of(f)
        # candidate present columns for this field's quantity class (grounded alternatives, all pre-verified present)
        cands = by_quantity.get(quantity, [])
        bind_col = None
        alts = []
        if req_col and req_col in present_cols:
            bind_col = req_col                                   # AI named a real present column → bind straight
        elif len(cands) == 1:
            bind_col = cands[0].get("column_name")               # unique present column for the class → PRE binds it
        else:
            for c in cands:
                alts.append({"kind": "column", "name": c.get("column_name"),
                             "fidelity": "real_exact"})
        blank_reason = None if (bind_col or alts) else "structurally_null"
        facts.append({
            "slot": f.get("slot") or (f.get("target_column") or metric or f"field_{i}"),
            "metric": metric,
            "requested_column": req_col,
            "present": bool(bind_col or alts),
            "bind_column": bind_col,
            "alternatives": alts,
            "quantity": quantity,
            "unit": f.get("unit"),
            "blank_reason": blank_reason,
            "fidelity_note": None,
        })
    return facts


def _quantity_of(field):
    """A field's quantity class from its metric/unit (best-effort names-only; the routed map is the ground truth)."""
    m = (field.get("metric") or "").lower()
    u = (field.get("unit") or "").lower()
    for q, keys in (("energy", ("energy", "kwh", "kvarh", "mvah")),
                    ("power", ("power", "kw", "kva", "kvar", "load")),
                    ("voltage", ("voltage", "volt")),
                    ("current", ("current", "amp", "ampere")),
                    ("thd", ("thd", "harmonic")),
                    ("power_factor", ("pf", "power_factor", "factor"))):
        if any(k in m or k in u for k in keys):
            return q
    return None


def build_grounding(*, run_id, card_id, l1a, l1b, l2_out):
    """Assemble the per-card grounding bag (deterministic PRE). Returns the dict factsheet.build_factsheet consumes.

    Reads: l1b.asset (resolved meter/panel), l2_out.data_instructions (the story's requested metrics/endpoint), the
    catalog handling (resolver_scope), and the grounding/* engines. Every fact is a boolean / name / count / cause key —
    NO rendered number. Missing facts degrade to honest defaults so the sheet is always well-formed."""
    l1a = l1a or {}
    l2 = l2_out or {}
    asset = (l1b or {}).get("asset") or {}
    page_key = l1a.get("page_key")
    di = l2.get("data_instructions") or {}
    consumer = di.get("consumer") or {}
    resolver_scope = consumer.get("resolver_scope") or (asset.get("resolver_scope"))
    table = _asset_table(asset)

    g = {"asset": {"mfm_id": asset.get("mfm_id"), "asset_table": table, "table": table,
                   "mfm_name": asset.get("name") or asset.get("mfm_name"),
                   "resolver_scope": resolver_scope, "preferred_populated_dup": asset.get("preferred_populated_dup")}}

    # --- schema fingerprint + meaningful-data verdict (the ONE shared has_meaningful_data probe) --------------------
    try:
        g["schema_fingerprint"] = _fp.fingerprint(table) if table else None
    except Exception:
        g["schema_fingerprint"] = None
    try:
        mprobe = _meaningful.probe(asset, page_key)
    except Exception as e:
        mprobe = {"ok": False, "present": False, "meaningful": False, "cause": f"probe_error:{type(e).__name__}"}
    g["meaningful"] = bool(mprobe.get("ok"))
    g["meaningful_reason"] = mprobe.get("cause")
    g["table_has_rows"] = bool(mprobe.get("present"))

    # --- metric-class feasibility (does the table expose the PAGE's required column class) --------------------------
    try:
        cg = _metric_class.class_gate(asset, page_key)
        g["class_present"] = {rc: (rc not in (cg.get("missing") or [])) for rc in (cg.get("required") or [])}
    except Exception:
        g["class_present"] = {}
    g["asset"]["role"], g["asset"]["section"] = (None, None)

    # --- nameplate presence (rated/contract/nominal flags; the actual numbers stay in POST) ------------------------
    try:
        npf = _np.resolve(asset)
    except Exception:
        npf = {}
    g["has_rated"] = bool(npf.get("has_rated"))
    g["has_contracted"] = npf.get("contracted_kva") is not None
    g["has_nominal_voltage"] = npf.get("nominal_voltage_ll") is not None
    g["nameplate_source"] = npf.get("source")
    g["asset"]["role"] = npf.get("role")
    g["asset"]["section"] = npf.get("section")
    g["asset"]["asset_category"] = npf.get("asset_category")

    # --- energy register (reversed-CT flag) + structurally-null metric names ---------------------------------------
    try:
        er = _energy.energy_register(table) if table else {}
    except Exception:
        er = {}
    g["reversed_ct"] = bool(er.get("reversed_ct"))
    g["denorm_garbage"] = (mprobe.get("cause") == "denorm_garbage")
    g["structurally_null_metrics"] = mprobe.get("missing_class") or []

    # --- window clamp (data-from-<date> flag; the DATE stays out of L3) ---------------------------------------------
    try:
        rng = _window.meter_range(table) if table else None
        g["window_since"] = (rng or {}).get("min") if isinstance(rng, dict) else None
    except Exception:
        g["window_since"] = None

    # --- topology / aggregate coverage (structural counts) ---------------------------------------------------------
    is_aggregate = resolver_scope in ("panel", "panel_aggregate", "site")
    g["is_aggregate"] = is_aggregate
    if is_aggregate and asset.get("mfm_id") is not None:
        try:
            cov = _aggregate.aggregate_coverage(asset.get("mfm_id"), meaningful=True)
            g["members_total"] = cov.get("expected_count")
            g["members_reporting"] = cov.get("reporting_count")
            g["has_topology"] = cov.get("status") != "orphan"
            g["incomer_verified"] = None                         # TOPO-02: never trust the inverted incoming set
        except Exception:
            g["members_total"] = g["members_reporting"] = None
            g["has_topology"] = None
            g["incomer_verified"] = None
    else:
        g["members_total"] = g["members_reporting"] = None
        g["has_topology"] = None
        g["incomer_verified"] = None

    # --- endpoint + expected shape (pre-validated vs the LIVE endpoint set) -----------------------------------------
    try:
        er2 = _endpoint.resolve(page_key, resolver_scope, panel_mfm_id=asset.get("mfm_id"), panel_table=table)
    except Exception:
        er2 = {}
    g["endpoint"] = er2.get("endpoint") or consumer.get("endpoint")
    g["expected_shape"] = er2.get("expected_shape")
    g["is_history"] = er2.get("is_history")
    g["endpoint_live"] = er2.get("endpoint_live")
    g["date_navigable"] = er2.get("is_history") and er2.get("endpoint_live")

    # --- per-slot facts (names/flags; no fetched numbers) ----------------------------------------------------------
    g["slot_facts"] = _slot_facts(table, di, page_key)
    g["resolver_scope"] = resolver_scope
    return g


# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#  L3 per-card fan-out — factsheet -> emit -> validate -> apply (one AI call; the rest deterministic)
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
def run_card_l3(run_id, card_id, l1a, l1b, l2_out):
    """The full PRE->L3->POST for ONE card. Returns the render envelope from apply_render_spec, augmented with the
    render_verdict/reason/coverage so run_3_all can log + the host can thread it. Never raises (caller isolates)."""
    page_key = (l1a or {}).get("page_key")
    grounding = build_grounding(run_id=run_id, card_id=card_id, l1a=l1a, l1b=l1b, l2_out=l2_out)
    fs = build_factsheet(run_id=run_id, card_id=card_id, grounding=grounding,
                         l2_out=l2_out, page_key=page_key)
    factsheet = fs["factsheet"]
    spec_raw = emit_render_spec(factsheet)                        # the ONE L3 AI call (fail-open {} → blank spec below)
    spec, issues = validate_render_spec(spec_raw, factsheet)      # returns (clean_spec, issues[]); coerces bad→honest_blank
    try:
        persist_render_spec(run_id, card_id, spec)               # cache the reviewable/overridable RenderSpec row
    except Exception:
        pass
    env = apply_render_spec(spec=spec, factsheet=factsheet,
                            exact_metadata=(l2_out or {}).get("exact_metadata"))
    env["card_id"] = card_id
    env["_pre_bound_count"] = len(fs.get("pre_bound") or [])
    if issues:
        env["_spec_issues"] = issues
    return env


def run_3_all(run_id, l1a, l1b, l2_all):
    """Fan L3 out over every card that Layer 2 produced (parallel; one emit per card, vLLM batches). Returns
    {card_id: render_envelope}. A card with no Layer-2 output, or an exception, honest-blanks with a machine reason —
    never a fabricated render."""
    l2_all = l2_all or {}
    if not l2_all:
        return {}
    tasks = {}
    for cid, l2_out in l2_all.items():
        if not isinstance(l2_out, dict) or l2_out.get("exception"):
            continue                                             # a Layer-2 crash → no L3 (host renders the L2 error)
        tasks[cid] = (lambda cid=cid, o=l2_out: run_card_l3(run_id, cid, l1a, l1b, o))
    if not tasks:
        return {}
    res = run_parallel(tasks)
    out = {}
    for cid, r in res.items():
        if isinstance(r, Exception):
            out[cid] = {"card_id": cid, "render_verdict": "honest_blank", "answerability": "none",
                        "reason": f"l3_exception: {type(r).__name__}: {r}", "slots": {},
                        "coverage_note": None, "date_control": "disabled", "watermark": "live",
                        "exception": f"{type(r).__name__}: {r}"}
        else:
            out[cid] = r
        e = out[cid]
        stage(run_id, "L3.card", id=cid, verdict=e.get("render_verdict"), answer=e.get("answerability"),
              slots=len(e.get("slots") or {}), date=e.get("date_control"),
              reason=(e.get("reason") or "")[:60], fail=e.get("exception"))
    return out
