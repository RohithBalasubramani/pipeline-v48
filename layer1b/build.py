"""layer1b/build.py — compose Layer 1b: asset resolve (+ picker round-trip) -> card-agnostic column basket. [spec section 2 L1b, contract 3]"""
import os

from layer1b.resolve.asset_resolve import resolve_asset
from layer1b.basket.column_basket import build_basket
from layer1b.basket.topology_siblings import expand_basket_with_siblings
from layer1b.schema import build_layer1b_output, validate_layer1b_output


def run_1b(prompt, asset_id=None):
    # ENV-PIN GUARD [hardening]: the PIPELINE_ASSET_ID env fallback is honored ONLY when explicitly opted in
    # (V48_ALLOW_ENV_PIN=1 — CLI/trace runs). In the long-running host a launch-time env value would otherwise
    # silently pin EVERY request to one asset. The API asset_id param is unaffected.
    if asset_id is None and os.environ.get("V48_ALLOW_ENV_PIN") == "1":
        asset_id = os.environ.get("PIPELINE_ASSET_ID") or None
    resolved = resolve_asset(prompt, asset_id)
    asset = resolved.get("asset")
    basket = build_basket(prompt, asset) if asset else \
        {"tables": [], "columns": [], "probable": [], "n_columns": 0}
    # AGGREGATE PANEL: attach the full populated member-feeder fan-out + coverage (N of M reporting) so aggregate/Sankey
    # cards sum every member, not just the one representative feeder column_basket used for schema. [TOPO-01..07, DS-08]
    if asset:
        basket = expand_basket_with_siblings(basket, asset)
    out = build_layer1b_output(resolved, basket)
    # CONTRACT TELEMETRY (annotate-only, never blocks — verdicts are telemetry): surface integrity violations
    # ('ambiguous but no candidate_list', 'resolved asset but empty column_basket') in the output + failure log
    # instead of shipping them unnoticed. [hardening: unused validator wired]
    problems = validate_layer1b_output(out)
    if problems:
        out["contract_problems"] = problems
        try:
            from obs.failures import record
            record("layer1b", "contract-violation", detail="; ".join(problems))
        except Exception:
            pass
    return out
