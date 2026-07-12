"""admin/search.py — prompt search: find past runs by what was asked.

Substring match (case-insensitive) over each run's prompt (response doc, falling back to the PROMPT stage line),
returning full RunSummary rows so every hit links straight into the trace viewer. Error search lives in
failures_report (one sink already carries every defect)."""
from admin import runs, store
from admin.config import in_window


def prompts(q, t_from=None, t_to=None, limit=50):
    needle = (q or "").lower().strip()
    hits = []
    for rid in store.run_ids():
        ts = store.last_ts(rid)
        if not in_window(ts, t_from, t_to):
            continue
        s = runs.summary(rid)
        if not needle or needle in (s.get("prompt") or "").lower():
            hits.append(s)
    hits.sort(key=lambda r: -(r["ts_epoch"] or 0))
    return hits[:max(0, int(limit))]
