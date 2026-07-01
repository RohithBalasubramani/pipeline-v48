"""layer1b/build.py — compose Layer 1b: asset resolve (+ picker round-trip) -> card-agnostic column basket. [spec section 2 L1b, contract 3]"""
import os

from layer1b.resolve.asset_resolve import resolve_asset
from layer1b.basket.column_basket import build_basket
from layer1b.basket.topology_siblings import expand_basket_with_siblings
from layer1b.schema import build_layer1b_output


def run_1b(prompt, asset_id=None):
    asset_id = asset_id or os.environ.get("PIPELINE_ASSET_ID") or None
    resolved = resolve_asset(prompt, asset_id)
    asset = resolved.get("asset")
    basket = build_basket(prompt, asset) if asset else \
        {"tables": [], "columns": [], "probable": [], "n_columns": 0}
    # AGGREGATE PANEL: attach the full populated member-feeder fan-out + coverage (N of M reporting) so aggregate/Sankey
    # cards sum every member, not just the one representative feeder column_basket used for schema. [TOPO-01..07, DS-08]
    if asset:
        basket = expand_basket_with_siblings(basket, asset)
    return build_layer1b_output(resolved, basket)
