"""validation/stagelogs.py — per-case stage-log capture (overwrite-safe snapshot of the pipeline's deterministic
run_id artifacts) + log-derived failure reason mining. Covers: always-archive of pipeline_/failures_ + notes,
the ai_ size policy (fail-only by default), the resume subdir, reason tokenization, and never-raise on absence."""
from __future__ import annotations

import json
import os

import pytest

from sweep import config
from sweep import stagelogs

RID = "r_abc123def0"


@pytest.fixture()
def log_env(tmp_path, monkeypatch):
    logs = tmp_path / "logs"
    notes = tmp_path / "notes"
    logs.mkdir()
    notes.mkdir()
    monkeypatch.setattr(config, "PIPELINE_LOG_DIR", str(logs))
    monkeypatch.setattr(config, "NOTES_DIR", str(notes))
    monkeypatch.setattr(config, "ARCHIVE_AI", "fail")
    (logs / f"pipeline_{RID}.jsonl").write_text(
        json.dumps({"ts": 1.0, "stage": "PROMPT", "text": "x"}) + "\n"
        + json.dumps({"ts": 2.0, "stage": "layer1b", "ERROR": "RuntimeError: DB error"}) + "\n")
    (logs / f"failures_{RID}.jsonl").write_text(
        json.dumps({"run_id": RID, "stage": "llm", "reason": "timeout", "detail": "l2_emit 150s"}) + "\n"
        + json.dumps({"run_id": RID, "stage": "llm", "reason": "timeout", "detail": "again"}) + "\n"
        + json.dumps({"run_id": RID, "stage": "exec", "reason": "card_fail"}) + "\n")
    (logs / f"ai_{RID}.jsonl").write_text(json.dumps({"run_id": RID, "url": ":8200"}) + "\n")
    (logs / f"response_{RID}.json").write_text("{}")
    (notes / f"{RID}.json").write_text(json.dumps({"loop1": [], "loop2": None}))
    return str(tmp_path)


def test_reasons_tokenized_and_counted(log_env):
    r = stagelogs.reasons(RID)
    assert r == {"exec:card_fail": 1, "layer1b:stage_error": 1, "llm:timeout": 2}


def test_capture_failed_case_archives_everything_but_response(log_env, tmp_path):
    sdir = str(tmp_path / "session")
    s = stagelogs.capture(sdir, "case1", RID, failed=True)
    assert s["archived"] == [f"ai_{RID}.jsonl", f"failures_{RID}.jsonl",
                             f"notes_{RID}.json", f"pipeline_{RID}.jsonl"]
    assert s["skipped"] == []                          # response_ is silently out of scope, never 'skipped'
    assert s["log_reasons"]["llm:timeout"] == 2
    dest = os.path.join(sdir, "stagelogs", "case1")
    assert sorted(os.listdir(dest)) == s["archived"]


def test_capture_passed_case_skips_big_ai_log(log_env, tmp_path):
    s = stagelogs.capture(str(tmp_path / "s2"), "case2", RID, failed=False)
    assert f"ai_{RID}.jsonl" in s["skipped"]
    assert f"pipeline_{RID}.jsonl" in s["archived"]


def test_capture_resume_subdir_and_absent_run(log_env, tmp_path):
    sdir = str(tmp_path / "s3")
    s = stagelogs.capture(sdir, "case3", RID, failed=True, subdir="resume")
    assert os.path.isdir(os.path.join(sdir, "stagelogs", "case3", "resume"))
    assert s["archived"]
    # a run that never logged (or run_id None) is an honest empty summary, not an error
    assert stagelogs.capture(sdir, "case4", "r_nope000000", failed=True)["archived"] == []
    assert stagelogs.capture(sdir, "case5", None, failed=True) == {"archived": [], "skipped": [], "log_reasons": {}}
