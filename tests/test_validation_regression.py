"""validation/regression.py — session-vs-session diff: bucket truth (new_fail/fixed/still_*/degraded moves),
corpus-drift honesty (only_in_*), verdict gating (new_fail flips it, degraded moves do NOT), and never-raise."""
from __future__ import annotations

import json
import os

import pytest

from sweep import config
from sweep import regression


def _write_case(root: str, sid: str, cid: str, *, passed: bool, degraded: bool = False,
                stage: str | None = None, outcome: str = "cards", elapsed: float = 1.0) -> None:
    d = os.path.join(root, "sessions", sid, "cases")
    os.makedirs(d, exist_ok=True)
    rec = {"case": {"id": cid, "category": "single_asset", "prompt": f"prompt {cid}"},
           "judgment": {"pass": passed, "degraded": degraded, "stage": stage,
                        "why": "as expected" if passed else "boom"},
           "parsed": {"outcome": outcome, "payload_errors": 0},
           "elapsed_s": elapsed}
    with open(os.path.join(d, f"{cid}.json"), "w") as f:
        json.dump(rec, f)


@pytest.fixture()
def out_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUT_DIR", str(tmp_path))
    return str(tmp_path)


def test_buckets_and_verdict(out_dir):
    # baseline: a pass, b fail, c pass, d pass(clean), e only-in-baseline
    _write_case(out_dir, "base", "a", passed=True)
    _write_case(out_dir, "base", "b", passed=False, stage="routing")
    _write_case(out_dir, "base", "c", passed=True)
    _write_case(out_dir, "base", "d", passed=True)
    _write_case(out_dir, "base", "e", passed=True)
    # session: a fails (NEW), b passes (FIXED), c still passes, d degrades, f only-in-session
    _write_case(out_dir, "cur", "a", passed=False, stage="layer2_emit", elapsed=3.0)
    _write_case(out_dir, "cur", "b", passed=True)
    _write_case(out_dir, "cur", "c", passed=True)
    _write_case(out_dir, "cur", "d", passed=True, degraded=True, stage="infra")
    _write_case(out_dir, "cur", "f", passed=False, stage="transport")

    rep = regression.compare("base", "cur")
    assert rep["verdict"] == "regression"
    assert [r["case_id"] for r in rep["new_fail"]] == ["a"]
    assert rep["new_fail"][0]["session"]["stage"] == "layer2_emit"
    assert [r["case_id"] for r in rep["fixed"]] == ["b"]
    assert rep["counts"]["still_pass"] == 2          # c and d (a degraded pass is still a pass; b is 'fixed')
    assert [r["case_id"] for r in rep["newly_degraded"]] == ["d"]
    assert rep["only_in_baseline"] == ["e"] and rep["only_in_session"] == ["f"]
    assert rep["counts"]["compared"] == 4
    # mirrored to the session dir
    with open(os.path.join(out_dir, "sessions", "cur", "regression.json")) as f:
        assert json.load(f)["verdict"] == "regression"


def test_degraded_moves_never_flip_verdict(out_dir):
    _write_case(out_dir, "base", "a", passed=True)
    _write_case(out_dir, "cur", "a", passed=True, degraded=True, stage="infra")
    rep = regression.compare("base", "cur")
    assert rep["verdict"] == "ok"
    assert rep["counts"]["newly_degraded"] == 1


def test_empty_sides_degrade_honestly(out_dir):
    rep = regression.compare("nope_a", "nope_b")
    assert rep["verdict"] == "ok"
    assert rep["counts"]["compared"] == 0
    assert rep["latency_s"]["baseline"]["mean"] is None
