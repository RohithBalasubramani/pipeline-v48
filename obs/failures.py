"""obs/failures.py — append-only failure recorder (NO reloop/re-route). [#17]

Output dir resolves per call through obs/paths.py (V48_OBS_DIR-aware) so pytest telemetry lands in a throwaway
dir structurally, never the prod console sink [audit 2026-07-14, 03]. Defense-in-depth: under pytest a
real-shaped rid (harness-minted r_<10hex>) is prefixed `t_` — it fails admin RUN_ID_RE so it can never surface
in the console even if the env redirect is somehow absent; filename and record field stay in agreement."""
import json
import os
import re
from datetime import datetime

from obs.paths import logs_dir as _logs_dir

_REAL_RID_RE = re.compile(r"^r_[0-9a-f]{10}$")


def record(stage, reason, *, card_id=None, group_id=None, detail="", run_id="default"):
    if "PYTEST_CURRENT_TEST" in os.environ and _REAL_RID_RE.match(str(run_id)):
        run_id = f"t_{run_id}"
    out = _logs_dir()
    os.makedirs(out, exist_ok=True)
    rec = {
        "ts": datetime.now().isoformat(), "run_id": run_id, "stage": stage,
        "card_id": card_id, "group_id": group_id, "reason": reason, "detail": str(detail)[:300],
    }
    with open(os.path.join(out, f"failures_{run_id}.jsonl"), "a") as f:
        f.write(json.dumps(rec) + "\n")
    return rec
