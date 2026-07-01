"""validate/build.py — run_validate: the NON-AI data+payload validation layer (after 1a∥1b, before Layer 2).

Inputs: layer1a output (selected cards + page_key) + layer1b output (asset + column basket).
Pure pandas/deterministic. Emits per-column + per-card verdicts; on-failure POLICY deferred (annotate-only).
"""
from config.databases import CMD_CATALOG
from config.validation import FAILURE_POLICY
from validate.data_load import load_asset_frame
from validate.data_validate import validate_data
from validate.payload_lookup import card_payloads_for
from validate.payload_validate import validate_payloads
from validate.report import assemble


def _empty_data():
    return {"rows": 0, "span": None, "columns": [],
            "summary": {"n_columns": 0, "n_pass": 0, "n_warn": 0, "n_fail": 0}}


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
        df, _loaded = load_asset_frame(table, [c["column"] for c in cols])
        data_report = validate_data(df, cols)
    else:
        data_report = _empty_data()

    page_key = a.get("page_key")
    selected = a.get("cards") or []
    payload_report = validate_payloads(selected, lambda cid: card_payloads_for(cid, page_key), data_report)

    return assemble(asset, page_key, how, data_report, payload_report, policy=FAILURE_POLICY)
