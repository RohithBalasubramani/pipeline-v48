"""validation/runner.py request legs — pinned-case bodies (asset_id / asset_ids) and the unexpected-picker RESUME
diagnostic (re-POST pinned to the first has_data candidate; original judgment stands; expected-picker cases never
resume). Fully offline: _post is monkeypatched; stage-log capture runs against an empty log dir (honest no-op)."""
from __future__ import annotations

import json
import os

import pytest

from validation import config
from validation import runner


def _cards_raw(rid: str = "r_cards00000") -> dict:
    return {"ok": True, "run_id": rid, "page": {"page_key": "ups-asset-dashboard/battery-autonomy"},
            "asset": {"asset": {"name": "UPS-01", "class": "UPS"}, "how": "user-choice", "candidates": []},
            "cards": [{"card_id": 1, "payload": {"v": 1},
                       "render": {"verdict": "render", "leaf_stats": {"real": 3, "data": 4}}}]}


def _picker_raw(rid: str = "r_picker0000") -> dict:
    return {"ok": True, "run_id": rid, "cards": [],
            "asset": {"how": "ambiguous",
                      "candidates": [{"mfm_id": 99, "name": "HHF-01 (dark)", "has_data": False},
                                     {"mfm_id": 11, "name": "GIC-01-N3-UPS-01", "has_data": True}]}}


class _Env:
    def __init__(self):
        self.posts: list[dict] = []
        self.responses: list[dict] = []

    def post(self, path: str, body: dict, timeout: float) -> dict:
        self.posts.append(dict(body))
        return self.responses.pop(0)


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUT_DIR", str(tmp_path / "out"))
    monkeypatch.setattr(config, "PIPELINE_LOG_DIR", str(tmp_path / "logs"))   # empty: capture is an honest no-op
    monkeypatch.setattr(config, "NOTES_DIR", str(tmp_path / "notes"))
    e = _Env()
    monkeypatch.setattr(runner, "_post", e.post)
    return e


def test_pinned_bodies(env):
    env.responses = [_cards_raw(), _cards_raw("r_cards00001")]
    cases = [{"id": "c1", "category": "single_asset", "prompt": "ups status", "expect": "cards", "pin": 11},
             {"id": "c2", "category": "compare_2", "prompt": "compare a and b", "expect": "cards", "pins": [11, 12]}]
    runner.run_cases(cases, "s_pin", concurrency=1)
    bodies = {b.get("asset_id") or tuple(b.get("asset_ids") or ()): b for b in env.posts}
    assert bodies[11]["prompt"] == "ups status"
    assert bodies[(11, 12)]["asset_ids"] == [11, 12]


def test_unexpected_picker_fires_resume_and_original_judgment_stands(env):
    env.responses = [_picker_raw(), _cards_raw("r_resume0000")]
    cases = [{"id": "c3", "category": "single_asset", "prompt": "GIC-01-N3-UPS-01 load", "expect": "cards"}]
    manifest = runner.run_cases(cases, "s_resume", concurrency=1)
    assert len(env.posts) == 2
    assert env.posts[1]["asset_id"] == 11                      # first has_data candidate, not the dark one
    with open(os.path.join(config.OUT_DIR, "sessions", "s_resume", "cases", "c3.json")) as f:
        rec = json.load(f)
    assert rec["judgment"]["pass"] is False                    # diagnostic leg never rescues the judgment
    assert rec["judgment"]["stage"] == "asset_resolution"
    assert rec["resume"]["asset_id"] == 11
    assert rec["resume"]["judgment"]["pass"] is True
    assert manifest["resume_legs"] == 1 and manifest["resume_completed"] == 1
    assert os.path.isfile(os.path.join(config.OUT_DIR, "sessions", "s_resume", "raw", "c3.resume.json"))


def test_expected_picker_never_resumes(env):
    env.responses = [_picker_raw()]
    cases = [{"id": "c4", "category": "ambiguous", "prompt": "UPS-01", "expect": "picker"}]
    manifest = runner.run_cases(cases, "s_amb", concurrency=1)
    assert len(env.posts) == 1                                 # no second leg
    assert manifest["passed"] == 1 and manifest["resume_legs"] == 0
