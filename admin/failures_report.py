"""admin/failures_report.py — failure report + error search over failures_<run_id>.jsonl.

The failures sink is comprehensive by construction: obs/stage.py mirrors every defect-shaped stage field
(ERROR/fail/ok=False/gap/gaps) into it, and llm/client.py records classified LLM failures — so one sink answers both
"what breaks most" (aggregates) and "find this error" (substring search over reason+detail+stage).

One deliberate non-failure lives in the same sink: config/reason_templates.py mirrors every per-leaf honest-blank
REASON (stage=="reason") into failures_<rid>.jsonl — telemetry, not defects, and ~99% of the records. report()
therefore classifies: stage=="reason" → the blank_reasons bucket; everything else → the real-failure aggregates.

Reading the real counts (entry-level validation 2026-07-12, console_validation/failures.md):
  · layer-exception and stage_error are 1:1 twins (harness record() + the stage-span ERROR mirror both fire),
    so N of each ≈ N underlying exceptions, not 2N.
  · fill_gap mirrors each run-level answerability gap at layer2/reflect/notes (×3) plus per-card records.
  · records dated before 2026-07-12 ~17:00 in over_budget/no_json/truncated/transport are pytest artifacts that
    leaked under real-shaped rids (fixed: tests/conftest.py re-pins the obs run id per test)."""
from datetime import datetime

from admin import store
from admin.config import in_window, iso

BLANK_STAGE = "reason"            # honest-blank reason telemetry marker (writer: config/reason_templates.py)
BLANK_TOP_REASONS = 25
BLANK_RECENT = 50
HONEST_GAP_RECENT = 50

# Frozen ceiling for the historical pytest-leak quarantine [audit 2026-07-14, 03]: the conftest re-pin fix went
# live at ~17:00 on 2026-07-12 and the sink has been env-isolated (obs/paths.py) since. Records at/after the
# cutoff NEVER quarantine — a future leak must be caught by the paths redirect, not silently hidden here.
PYTEST_LEAK_CUTOFF = "2026-07-12T17:00:00"


def classify(r):
    """ONE classification home for a failures row (admin/explorer.py shares it) [audit 2026-07-14]:
      'blank'           — stage=="reason": per-leaf honest-blank telemetry (writer: config/reason_templates.py)
      'honest_gap'      — per-card answerability gap (reason fill_gap, stage L2.card): a VALID honest terminal
                          (run/harness reflect contract; admin/coverage._FILL_REASONS agrees), not a defect
      'gap_mirror'      — historical run-level fill_gap mirrors (layer2/reflect/notes/preflight_reroute rows);
                          write-side collapsed 2026-07-15, rows before that would quadruple-count one gap
      'twin'            — historical reason=='layer-exception' rows: each was written back-to-back with a
                          stage_error mirror for the SAME exception; counting both doubled every DB outage
      'pytest_artifact' — pre-cutoff llm rows with the impossible-in-prod 'stage=- ' detail prefix (every prod
                          call_qwen site passes stage=): unit-test residue leaked under real-shaped rids
      'real'            — everything else: the actual defect aggregates."""
    if r["stage"] == BLANK_STAGE:
        return "blank"
    if r["reason"] == "fill_gap":
        return "honest_gap" if r["stage"] == "L2.card" else "gap_mirror"
    if r["reason"] == "layer-exception":
        return "twin"
    if (r["stage"] == "llm" and str(r.get("detail") or "").startswith("stage=- ")
            and (r.get("ts") or "") < PYTEST_LEAK_CUTOFF):
        return "pytest_artifact"
    return "real"


def _rows(rid):
    files = store.files_for(rid)
    if "failures" not in files:
        return []
    out = []
    for rec in store.cached(files["failures"], store.jsonl) or []:
        try:
            ts = datetime.fromisoformat(str(rec.get("ts"))).timestamp()
        except (ValueError, TypeError):
            ts = None
        out.append({"run_id": rid, "ts_epoch": ts, "ts": iso(ts), "stage": rec.get("stage"),
                    "card_id": rec.get("card_id"), "reason": rec.get("reason"),
                    "detail": rec.get("detail")})
    return out


def report(t_from=None, t_to=None, reason=None, stage=None, q=None, limit=100):
    """Real failures (total/by_reason/by_stage/by_day/recent) + honest telemetry buckets, routed by classify():
    blank_reasons (per-leaf), honest_gaps (per-card answerability gaps), quarantined (frozen pytest artifacts,
    rows hidden), dedup (historical write-twin/mirror counts, excluded from aggregates). Window / reason /
    stage / needle filters apply identically to EVERY bucket before classification. Additive API: nothing the
    pre-2026-07-15 console read was removed."""
    by_reason, by_stage, by_day, matched = {}, {}, {}, []
    blank_by_reason, blank_matched = {}, []
    gap_by_day, gap_matched = {}, []
    quar_by_reason = {}
    total, blank_total, gap_total, quar_total = 0, 0, 0, 0
    dedup = {"layer_exception_twins": 0, "fill_gap_mirrors": 0}
    needle = q.lower() if q else None
    for rid in store.run_ids():
        for r in _rows(rid):
            if not in_window(r["ts_epoch"], t_from, t_to):
                continue
            if reason and r["reason"] != reason:
                continue
            if stage and r["stage"] != stage:
                continue
            if needle and needle not in " ".join(str(r.get(k) or "") for k in ("reason", "detail", "stage")).lower():
                continue
            cls = classify(r)
            if cls == "blank":
                blank_total += 1
                blank_by_reason[r["reason"]] = blank_by_reason.get(r["reason"], 0) + 1
                blank_matched.append(r)
            elif cls == "honest_gap":
                gap_total += 1
                day = (r["ts"] or "unknown")[:10]
                gap_by_day[day] = gap_by_day.get(day, 0) + 1
                gap_matched.append(r)
            elif cls == "gap_mirror":
                dedup["fill_gap_mirrors"] += 1
            elif cls == "twin":
                dedup["layer_exception_twins"] += 1
            elif cls == "pytest_artifact":
                quar_total += 1
                quar_by_reason[r["reason"]] = quar_by_reason.get(r["reason"], 0) + 1
            else:
                total += 1
                by_reason[r["reason"]] = by_reason.get(r["reason"], 0) + 1
                by_stage[r["stage"]] = by_stage.get(r["stage"], 0) + 1
                day = (r["ts"] or "unknown")[:10]
                by_day[day] = by_day.get(day, 0) + 1
                matched.append(r)
    matched.sort(key=lambda r: -(r["ts_epoch"] or 0))
    blank_matched.sort(key=lambda r: -(r["ts_epoch"] or 0))
    gap_matched.sort(key=lambda r: -(r["ts_epoch"] or 0))
    recent = matched[:max(0, int(limit))]
    blank_recent = blank_matched[:BLANK_RECENT]
    gap_recent = gap_matched[:HONEST_GAP_RECENT]
    for r in recent + blank_recent + gap_recent:
        r.pop("ts_epoch", None)
    return {
        "total": total,
        "by_reason": [{"reason": k, "count": v} for k, v in sorted(by_reason.items(), key=lambda kv: -kv[1])],
        "by_stage": [{"stage": k, "count": v} for k, v in sorted(by_stage.items(), key=lambda kv: -kv[1])],
        "by_day": [{"day": k, "count": v} for k, v in sorted(by_day.items())],
        "recent": recent,
        "blank_reasons": {
            "total": blank_total,
            "by_reason": [{"reason": k, "count": v}
                          for k, v in sorted(blank_by_reason.items(), key=lambda kv: -kv[1])[:BLANK_TOP_REASONS]],
            "recent": blank_recent,
        },
        "honest_gaps": {
            "total": gap_total,
            "by_day": [{"day": k, "count": v} for k, v in sorted(gap_by_day.items())],
            "recent": gap_recent,
        },
        "quarantined": {
            "total": quar_total,
            "by_reason": [{"reason": k, "count": v} for k, v in sorted(quar_by_reason.items(), key=lambda kv: -kv[1])],
        },
        "dedup": dedup,
    }
