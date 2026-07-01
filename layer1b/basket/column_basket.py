"""layer1b/basket/column_basket.py — CARD-AGNOSTIC generous column basket (resolve_columns, recipe_fields=None). [spec section 2 L1b, #20]"""
import os

from llm.client import call_qwen
from config.metrics import normalize_metric
from layer1b.basket.col_dict import col_dict, real_table_cols, latest_nonnull
from layer1b.resolve.asset_candidates import feeder_table

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_prompt(name):
    with open(os.path.join(_HERE, "prompts", name)) as f:
        return f.read()


def build_basket(prompt, asset, intent="snapshot"):
    # need only a resolved data TABLE — col_dict reads its real columns directly (neuract is self-describing). The old
    # `mfm_type_id` requirement was stale (col_dict was once keyed by mfm_type over lt_parameter; it no longer is) and
    # the live app_devices registry leaves mfm_type_id=None (class carries the type), so requiring it emptied every basket.
    if not asset or not asset.get("table"):
        return {"tables": [], "columns": [], "probable": [], "n_columns": 0}
    table = asset["table"]
    hasdata = latest_nonnull(table)
    # AGGREGATE PANEL only: when the panel's OWN table is an empty stub (pcc_panel_N_feedbacks) but it HAS feeders, build
    # the basket from a representative feeder's schema so the Sankey/total cards' metrics (active_power_total_kw, …)
    # resolve instead of hallucinating. A REAL meter (transformer/incomer) keeps its OWN columns — its table has data,
    # so we must NOT override it (doing so emptied the basket). leaf → no feeders → unchanged.
    if not hasdata and asset.get("has_feeders") and asset.get("mfm_id"):
        ft = feeder_table(asset["mfm_id"])
        if ft:
            table = ft
            hasdata = latest_nonnull(ft)
    metric = normalize_metric(prompt)                       # rough prompt-derived hint (1b is parallel to 1a)
    cols = col_dict(table)                                  # dictionary built from the REAL consumer (compat) columns
    lines = "\n".join(f"{c[0]} | {c[1]} | {c[2]} | {c[3]} | {'Y' if c[0] in hasdata else 'N'}" for c in cols)
    system = _load_prompt("column_system.md")
    user = (f"PROMPT: {prompt!r}\nMETRIC: {metric}\nINTENT: {intent}\n\n"
            f"COLUMNS (column_name | label | kind | unit | has_data):\n{lines}\n\nJSON:")
    res = call_qwen(system, user, timeout=120) or {}

    realset = {c[0] for c in cols}
    by = {c[0]: c for c in cols}
    feasible = [c for c in (res.get("feasible") or []) if c in realset]   # GENEROUS basket (no hallucination)
    # probable carries the AI's relevance CONFIDENCE (1.0=exact, 0.6-0.8=closest real stand-in) + substitute_for
    # (the asked-for concept a low-confidence column stands in for) so Layer 2 can best-effort fill + note substitutions.
    probable = []
    for p in (res.get("probable") or []):
        if not (isinstance(p, dict) and p.get("column") in realset):
            continue
        try:
            conf = float(p.get("confidence", 1.0))
        except (TypeError, ValueError):
            conf = 1.0
        probable.append({"column": p["column"], "label": p.get("label") or by[p["column"]][1],
                         "why": p.get("why") or "", "rank": p.get("rank"),
                         "confidence": max(0.0, min(1.0, conf)),
                         "substitute_for": (p.get("substitute_for") or None)})
    columns = [{"table": table, "column": col, "label": by[col][1], "kind": by[col][2],
                "unit": by[col][3], "has_data": col in hasdata} for col in feasible]
    return {"tables": [table], "columns": columns, "probable": probable,
            "n_columns": len(columns), "metric_hint": metric}
