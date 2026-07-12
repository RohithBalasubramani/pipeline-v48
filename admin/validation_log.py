"""admin/validation_log.py — validation report: the pre-L2 page verdicts per run + the external harness sessions.

Two sources: (1) each run's validation block (response summary: page verdict, column pass/warn/fail counts, policy)
plus the 'validate' stage line (expected_gap_frac); (2) outputs/validation/sessions/<sid>/ — the corpus harness's
manifest + judged cases (validation/runner.py artifacts)."""
import glob
import json
import os

from admin import runs, store
from admin.config import VALIDATION_DIR, in_window, iso


def run_rows(t_from=None, t_to=None):
    rows = []
    for rid in store.run_ids():
        ts = store.last_ts(rid)
        if not in_window(ts, t_from, t_to):
            continue
        resp = runs.response_summary(rid)
        if not resp:
            continue
        val = resp.get("validation") or {}
        if not val.get("verdict"):
            continue
        gap_frac = None
        for sl in reversed(runs.executions(rid)):
            for rec in sl:
                if rec.get("stage") == "validate":
                    gap_frac = rec.get("expected_gap_frac")
                    break
            if gap_frac is not None:
                break
        card_verdicts = {}
        for c in resp.get("cards") or []:
            v = c.get("validation_verdict")
            if v:
                card_verdicts[v] = card_verdicts.get(v, 0) + 1
        rows.append({"run_id": rid, "ts": iso(ts), "prompt": resp.get("prompt"),
                     "page_key": resp.get("page_key"), "verdict": val.get("verdict"), "how": val.get("how"),
                     "policy": val.get("policy"), "data_summary": val.get("data_summary"),
                     "payload_summary": val.get("payload_summary"), "expected_gap_frac": gap_frac,
                     "validation_blocked": resp.get("validation_blocked"), "card_verdicts": card_verdicts})
    rows.sort(key=lambda r: r["ts"] or "", reverse=True)
    return rows


def sessions():
    """Harness session summaries (manifest + per-case judgments), newest first."""
    out = []
    for mpath in glob.glob(os.path.join(VALIDATION_DIR, "sessions", "*", "manifest.json")):
        sdir = os.path.dirname(mpath)

        def _parse(_, sdir=sdir, mpath=mpath):
            with open(mpath) as f:
                manifest = json.load(f)
            cases = []
            for cpath in sorted(glob.glob(os.path.join(sdir, "cases", "*.json"))):
                try:
                    with open(cpath) as f:
                        c = json.load(f)
                except (ValueError, OSError):
                    continue
                parsed, judgment = c.get("parsed") or {}, c.get("judgment") or {}
                cases.append({"case_id": (c.get("case") or {}).get("id") or os.path.basename(cpath),
                              "prompt": (c.get("case") or {}).get("prompt"),
                              "run_id": parsed.get("run_id"), "outcome": parsed.get("outcome"),
                              "pass": judgment.get("pass"), "degraded": judgment.get("degraded"),
                              "stage": judgment.get("stage"), "why": judgment.get("why"),
                              "elapsed_s": c.get("elapsed_s")})
            return {"session": os.path.basename(sdir), "manifest": manifest, "cases": cases}

        s = store.cached(mpath, _parse)
        if s:
            out.append(s)
    out.sort(key=lambda s: (s["manifest"] or {}).get("finished_at") or "", reverse=True)
    return out
