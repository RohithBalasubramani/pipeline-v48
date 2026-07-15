"""tests/test_gap_sink_write_timing.py — blank-reason sink rows are written per SURVIVING gap, never per
construction (audit 2026-07-14, 10/11).

Historically every gap record hit failures_<rid>.jsonl the moment its sentence was built — before executor
fill, before _prune_stale_gaps, before the roster cap/dedup — so unbound_by_emit ran ~4.5× served truth and
roster no_reading floods hit ~50× (16,485 rows vs an 80 cap). Producers now build sentences via the PURE
config.reason_templates.sentence(); obs/gap_sink.record_gaps writes survivors at the serve boundary. Non-live."""
from __future__ import annotations

import json
import os


def _sink_rows(tmp_path, rid="default"):
    p = tmp_path / f"failures_{rid}.jsonl"
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]


def test_sentence_is_pure(tmp_path, monkeypatch):
    monkeypatch.setenv("V48_OBS_DIR", str(tmp_path))
    from config import reason_templates as rt
    monkeypatch.setattr(rt, "template", lambda cause: "{metric} left blank.")
    s = rt.sentence("unbound_by_emit", metric="apparent power")
    assert s == "apparent power left blank."
    assert _sink_rows(tmp_path) == []                          # NO side effect — that's the whole point


def test_reason_still_writes_for_event_callers(tmp_path, monkeypatch):
    monkeypatch.setenv("V48_OBS_DIR", str(tmp_path))
    from config import reason_templates as rt
    from obs import ai_log
    monkeypatch.setattr(ai_log, "_RUN_ID", "t_evt")
    monkeypatch.setattr(rt, "template", lambda cause: "{layer} failed.")
    rt.reason("pipeline_error", layer="layer1b")
    rows = _sink_rows(tmp_path, "t_evt")
    assert [(r["stage"], r["reason"]) for r in rows] == [("reason", "pipeline_error")]


def test_reconcile_slots_writes_nothing_at_l2(tmp_path, monkeypatch):
    monkeypatch.setenv("V48_OBS_DIR", str(tmp_path))
    from layer2.reconcile_slots import _reconcile_slots
    di = {"fields": []}
    catalog = [{"slot": f"data.readings.m{i}.value"} for i in range(10)]
    import layer2.emit.slot_catalog as SC
    monkeypatch.setattr(SC, "build_slot_catalog", lambda dp, b: catalog)   # local import inside the function
    _reconcile_slots(di, {"readings": {}}, None)
    assert di.get("_emit_gaps"), "the gap records themselves must still exist"
    assert _sink_rows(tmp_path) == []                          # ZERO sink lines at L2 — survivors write at serve


def test_roster_flood_writes_nothing_and_respects_cap(tmp_path, monkeypatch):
    monkeypatch.setenv("V48_OBS_DIR", str(tmp_path))
    from ems_exec.executor import roster_gaps as RG
    # a 1,000-point blank series_split — the historical ~50x flood shape
    values = [[{"ts": i, "hhf": None} for i in range(1000)]]
    state = {"specs": [{"slot": "chart.series", "mode": "series_split",
                        "series": [{"key": "hhf"}], "roster": []}]}
    out = {"chart": {"series": values[0]}}
    recs = RG.collect(out, {"_roster_state": state} if "_roster_state" else state)
    # whatever collect returns, the CAP bounds it and the sink saw NOTHING
    assert len(recs or []) <= 80 + 5
    assert _sink_rows(tmp_path) == []


def test_gap_sink_writes_exactly_the_survivors(tmp_path, monkeypatch):
    monkeypatch.setenv("V48_OBS_DIR", str(tmp_path))
    from obs import gap_sink, ai_log
    monkeypatch.setattr(ai_log, "_RUN_ID", "t_gsink")
    gaps = [
        {"slot": "a.value", "cause": "unbound_by_emit", "metric": "a", "reason": "a left blank."},
        {"slot": "a.value", "cause": "unbound_by_emit", "metric": "a", "reason": "dup — must dedup"},
        {"slot": "b.value", "cause": "no_reading", "metric": "b", "reason": "b no reading."},
        {"not_a_gap": True},
    ]
    gap_sink.record_gaps(gaps)
    rows = _sink_rows(tmp_path, "t_gsink")
    assert [(r["reason"], r["detail"]) for r in rows] == [
        ("unbound_by_emit", "a left blank."), ("no_reading", "b no reading.")]


def test_merge_emit_gaps_writes_only_appended_survivors(tmp_path, monkeypatch):
    monkeypatch.setenv("V48_OBS_DIR", str(tmp_path))
    from host.enrich import _merge_emit_gaps
    from obs import ai_log
    monkeypatch.setattr(ai_log, "_RUN_ID", "t_merge")
    payload = {"data": {"filled": {"value": 42.0}, "blank": {"value": None}}}
    emit_gaps = [
        {"slot": "data.filled.value", "cause": "unbound_by_emit", "metric": "filled", "reason": "stale — filled real"},
        {"slot": "data.blank.value", "cause": "unbound_by_emit", "metric": "blank", "reason": "blank survived."},
    ]
    merged = _merge_emit_gaps([], emit_gaps, payload)
    assert [g["slot"] for g in merged] == ["data.blank.value"]  # the filled leaf's record was pruned
    rows = _sink_rows(tmp_path, "t_merge")
    assert [(r["reason"], r["detail"]) for r in rows] == [("unbound_by_emit", "blank survived.")]
