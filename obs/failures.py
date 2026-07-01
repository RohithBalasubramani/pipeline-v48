"""obs/failures.py — append-only failure recorder (NO reloop/re-route). [#17]"""
import json
import os
from datetime import datetime

_OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs", "logs")


def record(stage, reason, *, card_id=None, group_id=None, detail="", run_id="default"):
    os.makedirs(_OUT, exist_ok=True)
    rec = {
        "ts": datetime.now().isoformat(), "run_id": run_id, "stage": stage,
        "card_id": card_id, "group_id": group_id, "reason": reason, "detail": str(detail)[:300],
    }
    with open(os.path.join(_OUT, f"failures_{run_id}.jsonl"), "a") as f:
        f.write(json.dumps(rec) + "\n")
    return rec
