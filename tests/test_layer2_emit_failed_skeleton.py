"""tests/test_layer2_emit_failed_skeleton.py — the INFRA-failure conforming-skeleton contract (audit 04 F1/F6).

A per-card EXCEPTION inside run_card (and an llm-stage timeout — pinned in test_layer2_per_leaf_payload_partition)
degrades to a CONFORMING skeleton: the card ships its real component with per-leaf 'emit_failed' reasons — no
hard_fail, no page reroute (a reroute re-runs N emits under the same contention/bug; proven waste). Knob
layer2.emit_failed_skeleton off = the historical _err lane, byte-preserved. Non-live."""
from __future__ import annotations

import pytest

import layer2.build as B
import layer2.emit_failed as EF


_CI = {"card_id": 61, "group_id": None, "is_group_card": False, "page_key": "p/x",
       "story": {"analytical_story": "s", "page_story": "", "template_card_ids": []},
       "column_basket": {"columns": []}, "asset": None, "swap_candidates": [],
       "catalog_row": {"default_payload": {"payload": {"reading": {"label": "X", "value": 7.0}},
                                           "payload_stripped": {"reading": {"label": "X", "value": None}}},
                       "feasibility": {}}}


def _fake_build_ci(run_id, card_id, l1a, l1b, shared_ctx_ref=None):
    return dict(_CI)


def test_raising_emit_returns_conforming_skeleton(monkeypatch):
    monkeypatch.setattr(B, "build_card_input", _fake_build_ci)
    monkeypatch.setattr(B, "emit", lambda ci, feedback=None: (_ for _ in ()).throw(RuntimeError("boom-in-emit")))
    out = B.run_card("t_rid", 61, {}, {})
    assert out["conforms"] is True and out["failure"] is None
    assert (out.get("_emit_failed") or {}).get("stage") == "llm"
    assert "boom-in-emit" in ((out.get("_emit_failed") or {}).get("detail") or "")
    # satisfies the exec-cards skip predicate: not o.get("exception") and exact_metadata is not None
    assert "exception" not in out and out.get("exact_metadata") is not None
    assert out["gap"] is False and out["answerability"] == "partial"


def test_page_of_skeletons_counts_zero_hard_fails(monkeypatch):
    monkeypatch.setattr(B, "build_card_input", _fake_build_ci)
    monkeypatch.setattr(B, "emit", lambda ci, feedback=None: (_ for _ in ()).throw(RuntimeError("boom")))
    import run.layer2_all as LA
    l1a = {"cards": [{"card_id": 61}, {"card_id": 62}], "page_key": "p/x"}
    out = LA.run_2_all("t_rid2", l1a, {"asset": {"mfm_id": 1}})
    hard_fails = sum(1 for o in out.values() if not (o or {}).get("conforms"))
    assert hard_fails == 0                                      # no reroute trigger from the infra family


def test_reflect_never_reroutes_on_skeletons(monkeypatch):
    import run.harness as H
    calls = []
    monkeypatch.setattr(H, "run_1a", lambda *a, **k: calls.append("reroute") or {})
    skel = {"conforms": True, "gap": False, "answerability": "partial", "_emit_failed": {"stage": "llm"}}
    monkeypatch.setattr(H, "run_2_all", lambda rid, a, b: {61: dict(skel), 62: dict(skel)})
    out = {"errors": {}, "layer1a": {"page_key": "p/x", "cards": []}, "layer1b": {"asset": {}},
           "validation": {}, "notes": {}}
    H._reflect_loop(out, "prompt", "db", "t_rid3")
    assert calls == []                                          # zero page reroutes


def test_knob_off_reraises_to_the_err_lane(monkeypatch):
    monkeypatch.setattr(B, "build_card_input", _fake_build_ci)
    monkeypatch.setattr(B, "emit", lambda ci, feedback=None: (_ for _ in ()).throw(RuntimeError("boom-off")))
    monkeypatch.setattr(EF, "enabled", lambda: False)
    with pytest.raises(RuntimeError, match="boom-off"):
        B.run_card("t_rid4", 61, {}, {})


def test_skeleton_build_failure_reraises_original(monkeypatch):
    def bad_ci(*a, **k):
        raise KeyError("ci-broken")                              # build_card_input itself is the broken thing
    monkeypatch.setattr(B, "build_card_input", bad_ci)
    with pytest.raises(KeyError, match="ci-broken"):
        EF.skeleton_for_exception("t", 61, {}, {}, KeyError("ci-broken"))


def test_degrade_passes_through_emit_stage_failures():
    out = {"conforms": False, "failure": {"stage": "emit", "reason": "data_instructions.fields is empty"},
           "data_instructions": {}}
    assert EF.degrade(dict(out), _CI)["conforms"] is False       # gate failures keep the retry+reroute contract
