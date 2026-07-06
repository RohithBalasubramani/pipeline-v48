"""validate/report.py — roll per-column + per-card verdicts into one validation report. [validate]

PAGE-VERDICT ROLLUP [F1 fix]: a live meter almost always carries SOME dead/spare registers, so 'any column fail ⇒ page
fail' mis-flagged 10/25 healthy pages. The page verdict now distinguishes:
    fail            — ZERO usable columns/cards (nothing can render — matches the harness validation_blocked gate)
    pass_with_gaps  — real data present, some columns/cards dead (dead-column counts stay telemetry in the summary)
    warn / pass     — as before.
The legacy any-fail rollup is the DB knob validation.rollup_legacy_any_fail (default off)."""
from config.app_config import cfg

_ORDER = {"pass": 0, "warn": 1, "pass_with_gaps": 2, "fail": 3}


def _roll(summary):
    n = summary.get("n_columns", summary.get("n_cards", 0)) or 0
    n_pass, n_warn, n_fail = summary.get("n_pass", 0), summary.get("n_warn", 0), summary.get("n_fail", 0)
    if cfg("validation.rollup_legacy_any_fail", False):
        return "fail" if n_fail else ("warn" if n_warn else "pass")
    if n and n_fail and (n_pass + n_warn) == 0:
        return "fail"                                 # nothing usable at all — a genuine can't-render
    if n_fail:
        return "pass_with_gaps"                       # live page with dead leaves — telemetry, not a page failure
    return "warn" if n_warn else "pass"


def assemble(asset, page_key, how, data_report, payload_report, *, expected_gaps=None, n_cards=0, policy):
    if how in ("ambiguous", "empty") or not asset:
        overall = "asset_pending"                 # asset picker must resolve before data can be validated
    else:
        d, p = _roll(data_report["summary"]), _roll(payload_report["summary"])
        overall = max([d, p], key=lambda x: _ORDER[x])
    gaps = list(expected_gaps or [])
    return {
        "asset": asset and {"mfm_id": asset.get("mfm_id"), "name": asset.get("name"),
                            "table": asset.get("table")},
        "page_key": page_key,
        "how": how,
        "policy": policy,                          # what an on-failure action WOULD be (deferred; default annotate)
        "data": data_report,
        "payload": payload_report,
        # PRE-L2 known gaps (topology infeasibility) + the roll-up fraction the harness re-routes on BEFORE Layer 2
        "expected_gaps": gaps,
        "expected_gap_frac": round(len(gaps) / n_cards, 4) if n_cards else 0.0,
        "verdict": overall,
    }
