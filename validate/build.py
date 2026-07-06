"""validate/build.py — run_validate: THE one pre-Layer-2 validation pass (after 1a∥1b, BEFORE Layer 2).

TWO-PASS CONTRACT [validation-streamline]:
  PASS 1 (THIS, pre-L2, one run_validate): data availability (per-column verdicts over the newest PROBE_ROWS),
    payload supply-vs-demand (over the HARVESTED defaults — pre-emit by nature), and topology feasibility
    (expected_gaps — moved here from layer2/build so an infeasible page re-routes BEFORE the N-emit fan-out).
    The result is a MACHINE VERDICT Layer 2 CONSUMES: per-column verdicts are folded back into the 1b basket
    (gate_data_instructions/gate_roster treat a validate-FAIL column as unbindable; the emit prompt marks it), and
    the harness re-routes on expected_gap_frac before any emit.
  PASS 2 (in/post-L2, unchanged, genuinely post): emission-conformance gates (layer2/gates), swap settle, and the
    host per-leaf render verdicts. Do NOT move those here — they validate the EMISSION/RENDER, which doesn't exist yet.

Pure pandas/deterministic. On-failure POLICY deferred (annotate-only); per-LEAF degradation everywhere.
"""
from config.app_config import cfg
from config.databases import CMD_CATALOG
from config.validation import FAILURE_POLICY
from validate.data_load import load_asset_frame
from validate.data_validate import validate_data
from validate.handling_lookup import handling_class_for
from validate.payload_lookup import card_payloads_for
from validate.payload_validate import validate_payloads
from validate.report import assemble
from validate.schema import validate_validation_output


def _empty_data():
    return {"rows": 0, "span": None, "columns": [],
            "summary": {"n_columns": 0, "n_pass": 0, "n_warn": 0, "n_fail": 0}}


def _fold_into_basket(basket_cols, data_report):
    """Fold the per-column verdicts BACK into the 1b basket (in place) so Layer 2 consumes ONE truth: the basket's
    `has_data` stays the 1b window HINT; `verdict`/`usable`/`validate_reasons` are the authoritative pre-L2 probe.
    A validate-FAIL column then gates like a hallucinated one (per-leaf honest-blank with the validate reason)."""
    by_col = {c["column"]: c for c in data_report.get("columns") or []}
    for c in basket_cols:
        v = by_col.get(c.get("column"))
        if not v:
            continue
        c["verdict"] = v["verdict"]
        c["usable"] = v["verdict"] != "fail"
        if v.get("reasons"):
            c["validate_reasons"] = v["reasons"]


def _expected_gaps(selected, asset, how):
    """DETERMINISTIC topology-infeasibility, PRE-emit [moved from layer2/build._finalize]: a card that REQUIRES feeder
    topology (card_feasibility.required_topology/required_mesh) on an asset with NO feeders is a KNOWN gap before any
    LLM call — the harness re-routes on the roll-up instead of burning an N-emit fan-out and discovering it in reflect.
    Special-renderer classes (the fields-optional set) never count: their required_mesh is about the 3D/SLD chrome."""
    if not asset or how == "no_data":
        return []
    from config.gates_vocab import fields_optional_classes as _foc     # ONE shared accessor [A6a] — prompt/gate parity
    fields_optional = _foc()
    has_feeders = bool(asset.get("has_feeders"))
    gaps = []
    if has_feeders:
        return gaps
    from layer2.catalog.feasibility import read as read_feasibility     # lazy: validate must import without layer2 side-effects
    for c in selected:
        cid = c.get("card_id")
        if cid is None:
            continue
        feas = read_feasibility(cid)
        if not (feas.get("required_topology") or feas.get("required_mesh")):
            continue
        if handling_class_for(cid) in fields_optional:
            continue
        gaps.append({"card_id": cid, "title": c.get("title"), "cause": "topology_infeasible",
                     "reason": "card needs feeder topology; the resolved asset has no feeders"})
    return gaps


def run_validate(layer1a, layer1b, db=CMD_CATALOG):
    a, b = layer1a or {}, layer1b or {}
    asset = b.get("asset")
    how = b.get("how")
    basket = b.get("column_basket") or {}
    cols = basket.get("columns") or []
    # validate the table the BASKET actually selected — for an aggregate panel that is a representative FEEDER table
    # (the panel's own table is an empty pcc_panel_N stub), so the columns line up with real rows. Leaf assets: own table.
    table = (basket.get("tables") or [None])[0] or (asset.get("table") if asset else None)

    if asset and table and cols:
        df, _loaded, ordered = load_asset_frame(table, [c["column"] for c in cols])
        data_report = validate_data(df, cols, ordered=ordered)
        _fold_into_basket(cols, data_report)                   # ← Layer 2 consumes these (gates + emit prompt)
    else:
        data_report = _empty_data()

    page_key = a.get("page_key")
    selected = a.get("cards") or []
    payload_report = validate_payloads(selected, lambda cid: card_payloads_for(cid, page_key), data_report)

    try:
        expected_gaps = _expected_gaps(selected, asset, how)
    except Exception:                                          # feasibility rows unreadable → no pre-gap (annotate-only)
        expected_gaps = []

    report = assemble(asset, page_key, how, data_report, payload_report,
                      expected_gaps=expected_gaps, n_cards=len(selected), policy=FAILURE_POLICY)
    report["_schema_issues"] = validate_validation_output(report)   # wired self-check (annotate-only, like 1b/L2)
    return report


def payload_final(layer2, page_key, data_report):
    """POST-SETTLE telemetry refresh [report-staleness]: swaps (incl. forced renderability swaps) can change the FINAL
    card set after the pre-L2 report was scored. Re-run ONLY the payload supply-vs-demand over the cards that actually
    render, keyed by final render id. Annotate-only — never a gate."""
    cards = []
    for cid, o in (layer2 or {}).items():
        sd = (o or {}).get("swap_decision") or {}
        final_id = sd.get("swap_to_id") if (sd.get("origin") == "swapped" and sd.get("swap_to_id")) else cid
        cards.append({"card_id": int(final_id), "title": sd.get("swap_to_title")})
    return validate_payloads(cards, lambda cid: card_payloads_for(cid, page_key), data_report)
