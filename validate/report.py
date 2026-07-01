"""validate/report.py — roll per-column + per-card verdicts into one validation report. [validate]"""


def _roll(summary):
    if summary.get("n_fail"): return "fail"
    if summary.get("n_warn"): return "warn"
    return "pass"


def assemble(asset, page_key, how, data_report, payload_report, *, policy):
    if how in ("ambiguous", "empty") or not asset:
        overall = "asset_pending"                 # asset picker must resolve before data can be validated
    else:
        d, p = _roll(data_report["summary"]), _roll(payload_report["summary"])
        order = {"pass": 0, "warn": 1, "fail": 2}
        overall = max([d, p], key=lambda x: order[x])
    return {
        "asset": asset and {"mfm_id": asset.get("mfm_id"), "name": asset.get("name"),
                            "table": asset.get("table")},
        "page_key": page_key,
        "how": how,
        "policy": policy,                          # what an on-failure action WOULD be (deferred; default annotate)
        "data": data_report,
        "payload": payload_report,
        "verdict": overall,
    }
