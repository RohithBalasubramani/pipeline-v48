"""tests/test_obs_paths_isolation.py — STRUCTURAL test/prod telemetry isolation (obs/paths.py, audit 03).

Pins: (1) the pytest session redirects every obs WRITER to a throwaway dir via V48_OBS_DIR (set in conftest
before any obs import); (2) each writer honors the env per call; (3) a harness-minted real-shaped rid is
coerced to the t_ namespace under pytest (fails admin RUN_ID_RE — can never surface in the console) even if
the redirect were absent; (4) replay's override outranks env; (5) permanence meta-test — no obs writer may
hardcode the prod outputs dir again. Non-live."""
from __future__ import annotations

import json
import os
import re

import obs.paths as paths


def test_conftest_redirects_session_sink():
    prod = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs", "logs")
    assert os.environ.get("V48_OBS_DIR"), "conftest must set V48_OBS_DIR before any obs import"
    assert paths.logs_dir() != prod
    assert paths.notes_dir() != os.path.join(os.path.dirname(prod), "notes")


def test_writers_honor_v48_obs_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("V48_OBS_DIR", str(tmp_path))
    monkeypatch.setenv("V48_OBS_NOTES_DIR", str(tmp_path / "notes"))
    prod = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs", "logs")
    before = set(os.listdir(prod)) if os.path.isdir(prod) else set()

    from obs.failures import record
    from obs.stage import stage
    from obs import sink_jsonl, sql_trace, notes
    record("x", "y", run_id="isol_case", detail="d")
    stage("isol_case", "unit", ok=True)
    sink_jsonl.write({"trace_id": "isol_trace", "kind": "unit"})
    sql_trace.record("db", "SELECT 1", rows=1, ms=0.1)
    notes.record("isol_case", {"loop1": [{"card_id": 1, "answerability": "full", "note": "n"}], "loop2": None})

    got = set(os.listdir(tmp_path))
    assert "failures_isol_case.jsonl" in got
    assert "pipeline_isol_case.jsonl" in got
    assert "trace_isol_trace.jsonl" in got
    assert os.path.exists(tmp_path / "notes" / "isol_case.json")
    after = set(os.listdir(prod)) if os.path.isdir(prod) else set()
    assert not {f for f in after - before if "isol" in f}, "an isol-case file leaked into the prod dir"


def test_realshaped_rid_coerced_under_pytest(tmp_path, monkeypatch):
    monkeypatch.setenv("V48_OBS_DIR", str(tmp_path))
    from obs.failures import record
    rec = record("layer1b", "whatever", run_id="r_" + "a" * 10)
    assert rec["run_id"] == "t_r_aaaaaaaaaa"
    assert (tmp_path / "failures_t_r_aaaaaaaaaa.jsonl").exists()
    from admin.config import RUN_ID_RE
    assert not RUN_ID_RE.match(rec["run_id"]), "coerced rid must never look real to the console"
    row = json.loads((tmp_path / "failures_t_r_aaaaaaaaaa.jsonl").read_text().splitlines()[0])
    assert row["run_id"] == "t_r_aaaaaaaaaa"          # filename and record field agree


def test_replay_override_wins(tmp_path, monkeypatch):
    monkeypatch.setenv("V48_OBS_DIR", str(tmp_path / "env"))
    try:
        paths.set_override(str(tmp_path / "bundle"))
        assert paths.logs_dir() == str(tmp_path / "bundle")
        assert paths.notes_dir() == str(tmp_path / "bundle")   # notes default to the bundle (isolate behavior)
    finally:
        paths.clear_override()
    assert paths.logs_dir() == str(tmp_path / "env")


def test_isolate_redirects_through_the_door(tmp_path):
    from replay.isolate import redirect_legacy_writers
    try:
        d = redirect_legacy_writers(str(tmp_path))
        assert d == os.path.join(str(tmp_path), "legacy_logs")
        assert paths.logs_dir() == d
    finally:
        paths.clear_override()


def test_no_writer_bypasses_paths():
    """Permanence meta-test: the 'writer hardcodes the prod dir' defect class cannot silently return."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    writers = ["obs/failures.py", "obs/stage.py", "obs/ai_log.py", "obs/sql_trace.py",
               "obs/sink_jsonl.py", "obs/notes.py"]
    for rel in writers:
        src = open(os.path.join(root, rel)).read()
        assert "from obs.paths import" in src, f"{rel} must resolve its dir through obs/paths"
        assert not re.search(r'os\.path\.join\([^)]*"outputs"', src), f"{rel} hardcodes an outputs dir"
    server_src = open(os.path.join(root, "host/server.py")).read()
    dump = server_src.split("def _dump_response", 1)[1].split("\ndef ", 1)[0]
    assert "logs_dir()" in dump, "_dump_response must resolve through obs/paths"
