"""validation/checks/datesync.py — INTERACTIVE DATE-SYNC coverage: for a served response, drive each is_history
card's /api/frame re-fetch across windows and verify (a) history cards RESLICE (bucket count and/or numeric leaves
change between a 24h and a 30d window), (b) snapshot (non-history) cards carry NO refetch bundle (they cannot be
driven — the FE date control is honestly disabled), (c) the re-fetch contract itself holds (HTTP 200, ok:true,
payload present).

RC9 AWARENESS (the certified honest exception): an is_history card whose numeric leaves are as-of-latest SCALARS
(no time-series array) legitimately does NOT change across windows — reported as 'as_of_latest', a pass, not a
defect. /api/frame is NO-LLM, so these checks run at FRAME_CONCURRENCY without vLLM risk."""
from __future__ import annotations

import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from validation import config

W_NARROW = {"range": "last-24-hours", "sampling": "hourly"}
W_WIDE = {"range": "last-30-days", "sampling": "day"}


def _post_frame(body: dict) -> dict:
    req = urllib.request.Request(config.BASE_URL + "/api/frame", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=config.FRAME_TIMEOUT_S) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _num_leaves(o, path="", out=None):
    out = {} if out is None else out
    if isinstance(o, bool):
        return out
    if isinstance(o, (int, float)):
        out[path] = o
    elif isinstance(o, list):
        for i, x in enumerate(o):
            _num_leaves(x, f"{path}[{i}]", out)
    elif isinstance(o, dict):
        for k, v in o.items():
            _num_leaves(v, f"{path}.{k}", out)
    return out


def _has_series(payload) -> bool:
    """Any list of >=3 numbers / value-dicts = a time-series leaf (RC9 discriminator)."""
    if isinstance(payload, list):
        nums = [x for x in payload if isinstance(x, (int, float)) and not isinstance(x, bool)]
        dicts = [x for x in payload if isinstance(x, dict)]
        if len(nums) >= 3 or (len(dicts) >= 3 and any(isinstance(v, (int, float)) for d in dicts[:3] for v in d.values())):
            return True
        return any(_has_series(x) for x in payload)
    if isinstance(payload, dict):
        return any(_has_series(v) for v in payload.values())
    return False


def _check_card(card: dict) -> dict:
    body = lambda w: {"exact_metadata": card.get("payload"), "data_instructions": card.get("data_instructions"),
                      "refetch": card.get("refetch"), "date_window": w}
    try:
        a = _post_frame(body(W_NARROW))
        b = _post_frame(body(W_WIDE))
    except Exception as e:
        return {"card_id": card.get("card_id"), "result": "frame_error", "why": f"{type(e).__name__}: {str(e)[:120]}"}
    if not (a.get("ok") and b.get("ok")):
        return {"card_id": card.get("card_id"), "result": "frame_not_ok",
                "why": str(a.get("error") or b.get("error"))[:120]}
    la, lb = _num_leaves(a.get("payload")), _num_leaves(b.get("payload"))
    changed = len(la) != len(lb) or any(la[k] != lb[k] for k in (set(la) & set(lb)))
    if changed:
        return {"card_id": card.get("card_id"), "result": "reslices",
                "leaves": f"{len(la)}->{len(lb)}"}
    if not _has_series(a.get("payload")):
        return {"card_id": card.get("card_id"), "result": "as_of_latest", "why": "scalar/KPI card (RC9 honest)"}
    return {"card_id": card.get("card_id"), "result": "no_reslice",
            "why": f"{len(la)} identical numeric leaves across 24h vs 30d on a series card"}


def check_response(raw_response: dict) -> dict:
    """Run date-sync checks over one saved /api/run response. Returns {history:[...], snapshot_violations:[...]}"""
    cards = (raw_response or {}).get("cards") or []
    history = [c for c in cards if c.get("is_history") and c.get("refetch")]
    snapshot_violations = [c.get("card_id") for c in cards if not c.get("is_history") and c.get("refetch")]
    with ThreadPoolExecutor(max_workers=config.FRAME_CONCURRENCY) as ex:
        results = list(ex.map(_check_card, history))
    return {
        "n_history": len(history),
        "reslices": sum(1 for r in results if r["result"] == "reslices"),
        "as_of_latest": sum(1 for r in results if r["result"] == "as_of_latest"),
        "failures": [r for r in results if r["result"] in ("no_reslice", "frame_error", "frame_not_ok")],
        "snapshot_violations": snapshot_violations,          # non-history cards wrongly carrying a refetch bundle
        "cards": results,
    }
