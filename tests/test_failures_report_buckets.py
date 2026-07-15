"""tests/test_failures_report_buckets.py — failures_report.classify() + the routed console buckets (audit 2026-07-14).

The console's real-failure aggregates were ~4-5x inflated: layer-exception/stage_error write-twins (552 rows for
~276 events), quadruple-recorded honest fill-gaps (371 rows for 98 events), and 311 pre-2026-07-12T17:00 pytest
artifacts under real-shaped rids. classify() is the ONE report-side home that routes those out — raw jsonl is
NEVER rewritten (replay-safe). Fixture rids are dev-noise (r_testbuckets*) like test_admin_console. Non-live."""
from __future__ import annotations

import json
import os

from admin import config, failures_report


RID = "r_testbuckets1"


def _write_failures(rid, rows):
    p = os.path.join(config.LOGS_DIR, f"failures_{rid}.jsonl")
    os.makedirs(config.LOGS_DIR, exist_ok=True)
    with open(p, "w") as f:
        f.write("\n".join(json.dumps(x) for x in rows) + "\n")
    return p


def _cleanup(rid):
    p = os.path.join(config.LOGS_DIR, f"failures_{rid}.jsonl")
    if os.path.isfile(p):
        os.remove(p)


def _report_over(monkeypatch, rows, **kw):
    monkeypatch.setattr(failures_report.store, "run_ids", lambda sink="real": [RID])
    _write_failures(RID, rows)
    try:
        return failures_report.report(**kw)
    finally:
        _cleanup(RID)


def _row(stage, reason, ts="2026-07-14T10:00:00", card_id=None, detail=""):
    return {"ts": ts, "run_id": RID, "stage": stage, "card_id": card_id, "group_id": None,
            "reason": reason, "detail": detail}


def test_fill_gap_reclassified_honest(monkeypatch):
    rep = _report_over(monkeypatch, [
        _row("L2.card", "fill_gap", card_id=61, detail="requires temperature columns"),
        _row("layer2", "fill_gap", detail="gaps=1"),
        _row("reflect", "fill_gap", detail="gaps=1"),
        _row("notes", "fill_gap", detail="1"),
    ])
    assert rep["total"] == 0
    assert rep["honest_gaps"]["total"] == 1
    assert rep["honest_gaps"]["recent"][0]["detail"] == "requires temperature columns"
    assert rep["dedup"]["fill_gap_mirrors"] == 3


def test_layer_exception_twin_deduped(monkeypatch):
    rep = _report_over(monkeypatch, [
        _row("validation", "layer-exception", detail="RuntimeError: DB error"),
        _row("validate", "stage_error", detail="RuntimeError: DB error"),
    ])
    assert rep["total"] == 1
    assert rep["by_stage"] == [{"stage": "validate", "count": 1}]
    assert rep["dedup"]["layer_exception_twins"] == 1


def test_pytest_artifact_quarantined(monkeypatch):
    rep = _report_over(monkeypatch, [
        _row("llm", "over_budget", ts="2026-07-12T03:15:00",
             detail="stage=- prompt≈50 tok > llm.prompt_budget_tok=10 — call not sent"),
    ])
    assert rep["total"] == 0
    assert rep["quarantined"] == {"total": 1, "by_reason": [{"reason": "over_budget", "count": 1}]}
    assert rep["recent"] == []


def test_real_llm_failure_not_quarantined(monkeypatch):
    # the test_admin_console fixture shape: a REAL-shaped llm failure (stage=l2_emit prefix) stays a failure
    rep = _report_over(monkeypatch, [
        _row("llm", "timeout", ts="2026-07-11T00:00:03", detail="stage=l2_emit needle-xyz"),
    ])
    assert rep["total"] == 1
    assert rep["quarantined"]["total"] == 0


def test_post_cutoff_stageless_not_quarantined(monkeypatch):
    # the quarantine is FROZEN at the conftest-fix cutoff — a post-cutoff leak must show up as REAL (loud),
    # because the obs/paths redirect is what prevents leaks now, never a silent report-side hide
    rep = _report_over(monkeypatch, [
        _row("llm", "no_json", ts="2026-07-13T09:00:00", detail="stage=- no JSON object in the reply"),
    ])
    assert rep["total"] == 1
    assert rep["quarantined"]["total"] == 0


def test_classify_is_shared_with_explorer():
    src_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = open(os.path.join(src_root, "admin", "explorer.py")).read()
    assert "failures_report.classify" in src, "explorer must route through the ONE classification home"


def test_filters_apply_before_classification(monkeypatch):
    rep = _report_over(monkeypatch, [
        _row("L2.card", "fill_gap", card_id=61, detail="requires temperature columns"),
        _row("L2.card", "card_fail", card_id=24, detail="ValueError: boom"),
    ], reason="card_fail")
    assert rep["total"] == 1 and rep["honest_gaps"]["total"] == 0   # reason= filter excluded the gap row
