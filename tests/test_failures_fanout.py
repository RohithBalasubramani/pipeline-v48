"""obs failures fan-out [#17] — the fullsweep_20260706 telemetry gap (failures_ fired on 1/42 defect cards).

Two EXISTING funnels now mirror defect/degradation signals onto obs.failures without touching any layer's code:
  · obs/stage.py stage()            — ERROR=…, fail=…, ok=False, gap=…, gaps=N   (host exec / L2.card / reflect / …)
  · config/reason_templates.reason() — every generated per-leaf honest-blank sentence (fill._gap_sentence,
                                       layer2 unbound_by_emit, asset_3d no-model, …)
Both are telemetry-only: never raise, never alter what they pass through."""
import json
import os

from obs.stage import _failure_signal, stage

from obs.paths import logs_dir as _logs_dir   # writers resolve through the door — tests must read the same dir


def _read_failures(run_id):
    p = os.path.join(_logs_dir(), f"failures_{run_id}.jsonl")
    if not os.path.isfile(p):
        return []
    with open(p) as f:
        return [json.loads(line) for line in f if line.strip()]


def _cleanup(run_id):
    p = os.path.join(_logs_dir(), f"failures_{run_id}.jsonl")
    if os.path.isfile(p):
        os.remove(p)


# ── _failure_signal truth table (the data-driven stage vocabulary, no per-card logic) ───────────────────────────────
def test_failure_signal_vocabulary():
    assert _failure_signal({"ERROR": "ValueError: boom"}) == ("stage_error", "ValueError: boom")
    assert _failure_signal({"fail": "llm_timeout"}) == ("card_fail", "llm_timeout")
    assert _failure_signal({"ok": False, "why": "executor budget exceeded"}) == ("exec_fail", "executor budget exceeded")
    assert _failure_signal({"gap": "missing_kpis"}) == ("fill_gap", "missing_kpis")
    assert _failure_signal({"gaps": 3}) == ("fill_gap", "gaps=3")


def test_failure_signal_ignores_healthy_stages():
    assert _failure_signal({"ok": True}) is None
    assert _failure_signal({"gaps": 0}) is None
    assert _failure_signal({"gap": None, "fail": None}) is None
    assert _failure_signal({"page": "x/y", "cards": 4}) is None
    assert _failure_signal({"gaps": "not-a-number"}) is None       # malformed count never raises / never flags


# ── stage() → failures_<run_id>.jsonl fan-out ───────────────────────────────────────────────────────────────────────
def test_stage_fans_out_failures(capsys):
    rid = "t_fanout_stage"
    _cleanup(rid)
    try:
        stage(rid, "exec", card=60, ok=False, why="executor budget exceeded")
        stage(rid, "L2.card", id=24, fail="llm_timeout")
        stage(rid, "reflect", loop=1, gaps=2)
        stage(rid, "exec", card=61, ok=True)                        # healthy — must NOT be recorded
        recs = _read_failures(rid)
        assert [(r["stage"], r["reason"], r["card_id"]) for r in recs] == [
            ("exec", "exec_fail", 60), ("L2.card", "card_fail", 24), ("reflect", "fill_gap", None)]
        assert all(r["run_id"] == rid for r in recs)
    finally:
        _cleanup(rid)
        # stage() also appends pipeline_<rid>.jsonl — remove the test artifact
        p = os.path.join(_logs_dir(), f"pipeline_{rid}.jsonl")
        if os.path.isfile(p):
            os.remove(p)


# ── reason() → failures fan-out (the per-leaf honest-blank recording point) ─────────────────────────────────────────
def test_reason_channel_fans_out_failures(monkeypatch):
    from config import reason_templates as rt
    from obs import ai_log

    rid = "t_fanout_reason"
    monkeypatch.setattr(ai_log, "_RUN_ID", rid)
    monkeypatch.setattr(rt, "template", lambda cause: "{metric} not measured by this meter.")
    _cleanup(rid)
    try:
        s = rt.reason("column_absent", metric="oil_pressure_kpa")
        assert s == "oil_pressure_kpa not measured by this meter."   # the sentence is unchanged by the fan-out
        recs = _read_failures(rid)
        assert len(recs) == 1
        assert recs[0]["stage"] == "reason" and recs[0]["reason"] == "column_absent"
        assert "oil_pressure_kpa" in recs[0]["detail"]
    finally:
        _cleanup(rid)


def test_reason_unknown_cause_still_recorded_and_falls_back(monkeypatch):
    from config import reason_templates as rt
    from obs import ai_log

    rid = "t_fanout_reason_unknown"
    monkeypatch.setattr(ai_log, "_RUN_ID", rid)
    monkeypatch.setattr(rt, "template", lambda cause: None)
    _cleanup(rid)
    try:
        assert rt.reason("some_new_cause") == "some_new_cause"       # fallback = the cause key (channel never empty)
        recs = _read_failures(rid)
        assert len(recs) == 1 and recs[0]["reason"] == "some_new_cause"
    finally:
        _cleanup(rid)
