"""tests/test_failures_record_fidelity.py — failure-record fidelity (audit 01 F5, 05 F6).

Pins: (1) HEAD+TAIL detail truncation in the ONE recorder — a pandas/psql error prefixes the failing SQL, so a
front-only cut chopped the actual cause off every long-SQL record; the tail must survive. (2) llm failure
records carry the emitting card_id from the decision contextvar (llm_tap.set_decision) — without it every
timeout had card_id=null and could not be attributed to a card. Non-live."""
from __future__ import annotations

import json


def test_detail_head_tail_preserves_causal_tail(tmp_path, monkeypatch):
    monkeypatch.setenv("V48_OBS_DIR", str(tmp_path))
    from obs.failures import record
    sql = 'Execution failed on sql \'SELECT "timestamp_utc", ' + ", ".join(f'"col_{i}"' for i in range(60))
    detail = sql + " FROM t': server closed the connection UNIQUE-TAIL-TOKEN"
    rec = record("validate", "stage_error", run_id="clip_case", detail=detail)
    assert rec["detail"].startswith(detail[:120])
    assert " … " in rec["detail"]
    assert rec["detail"].endswith("UNIQUE-TAIL-TOKEN")          # the CAUSE survives the cut
    assert len(rec["detail"]) <= 300


def test_short_detail_unchanged(tmp_path, monkeypatch):
    monkeypatch.setenv("V48_OBS_DIR", str(tmp_path))
    from obs.failures import record
    rec = record("x", "y", run_id="clip_short", detail="exactly as written")
    assert rec["detail"] == "exactly as written"


def test_llm_record_carries_decision_card_id(monkeypatch):
    from obs import llm_tap
    import llm.client as C
    seen = []
    import obs.failures as F
    monkeypatch.setattr(F, "record", lambda stage, kind, **kw: seen.append((stage, kind, kw.get("card_id"))))
    llm_tap.set_decision(kind="selection", candidate_kind="swap_target", candidates=[], card_id=61)
    try:
        C._record("timeout", "l2_emit", "timed out (prompt≈22957 tok)")
    finally:
        llm_tap.clear_decision()
    C._record("timeout", "l2_emit", "no decision bound")        # outside a decision → card_id None, never raises
    assert seen == [("llm", "timeout", 61), ("llm", "timeout", None)]
