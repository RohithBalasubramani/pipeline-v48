"""tests/test_swap_criterion_story.py — T1-11 (criterion<->story swap gate + corrective re-emit) and the T1-12
flag-off byte-identity guard, unit-level against the REAL cmd_catalog (no live LLM).

  · DEFAULT OFF for BOTH features → the swap gate chain, the emit request, and the whole run path are byte-identical
    to the pre-T1-11/T1-12 behavior (the existing test_layer2_swap_gates a/b block stays green — see that file).
  · flag ON: a swap criterion must share >= 1 story-angle token with the card's analytical story, else the swap is
    rejected AND (uniquely) leaves a corrective reason build.py re-emits ONCE on; the gate fails OPEN when either the
    criterion or the story carries no comparable token.
"""
import pytest

from config.swap import MIN_CONFIDENCE
from data.db_client import q
from layer2.swap import gate_criterion_story
from layer2.swap.decide import gate as swap_gate

_BASE = dict(pool_ids=[99, 98], template_card_ids=[7], already_chosen=set(), page_card_ids=[5, 7],
             current_card_id=5)


def _swap(crit, conf=None, to=99):
    return {"action": "swap", "confidence": MIN_CONFIDENCE if conf is None else conf,
            "criterion": crit, "swap_to_id": to}


def _enable(monkeypatch):
    """Turn the criterion<->story gate ON for one test (restored on teardown)."""
    monkeypatch.setattr(gate_criterion_story, "enabled", lambda: True)


# ── flag OFF: byte-identical — the gate never rejects, never leaves a reason ───────────────────────
def test_off_ok_is_always_true():
    # disabled (default) → ok() returns True even for a criterion that shares no story token.
    assert gate_criterion_story.ok(_swap("sankey material flow"), "voltage harmonic distortion") is True


def test_off_swap_gate_swaps_a_mismatching_criterion_and_leaves_no_reason():
    d = swap_gate(_swap("sankey material flow"), **_BASE, story="voltage harmonic distortion")
    assert d["origin"] == "swapped" and "gate_reject" not in d


def test_off_swap_gate_without_story_kwarg_is_unchanged():
    # existing callers pass no `story` at all → default None → gate disabled → normal swap, no reason.
    d = swap_gate(_swap("hourly energy trend"), **_BASE)
    assert d["origin"] == "swapped" and "gate_reject" not in d


# ── flag ON: accept / reject / fail-open on gate_criterion_story.ok ────────────────────────────────
def test_on_accept_shared_token(monkeypatch):
    _enable(monkeypatch)
    assert gate_criterion_story.ok(_swap("hourly energy trend"), "energy consumption over month") is True


def test_on_reject_no_shared_token(monkeypatch):
    _enable(monkeypatch)
    assert gate_criterion_story.ok(_swap("sankey material flow"), "voltage harmonic distortion") is False


def test_on_fail_open_empty_story(monkeypatch):
    _enable(monkeypatch)
    assert gate_criterion_story.ok(_swap("hourly energy trend"), "") is True
    assert gate_criterion_story.ok(_swap("hourly energy trend"), None) is True


def test_on_fail_open_tokenless_criterion(monkeypatch):
    _enable(monkeypatch)
    # every criterion token is shorter than the min-token-len knob (default 4) → no comparable signal → fail open.
    assert gate_criterion_story.ok(_swap("ok hi go"), "energy consumption trend") is True
    assert gate_criterion_story.ok(_swap(""), "energy consumption trend") is True


# ── flag ON through decide.gate: reject normalizes to KEEP + stamps the corrective reason ──────────
def test_on_swap_gate_rejects_offangle_criterion_and_stamps_reason(monkeypatch):
    _enable(monkeypatch)
    d = swap_gate(_swap("sankey material flow"), **_BASE, story="voltage harmonic distortion")
    assert d["origin"] == "kept" and d["swap_to_id"] is None
    assert d["gate_reject"] == gate_criterion_story.reject_reason(_swap("sankey material flow"),
                                                                  "voltage harmonic distortion")


def test_on_swap_gate_accepts_onangle_criterion(monkeypatch):
    _enable(monkeypatch)
    d = swap_gate(_swap("hourly energy trend"), **_BASE, story="energy consumption over month")
    assert d["origin"] == "swapped" and "gate_reject" not in d


def test_on_other_gate_failure_stays_silent(monkeypatch):
    _enable(monkeypatch)
    # a LOW-confidence swap fails the cheap confidence gate FIRST — the criterion gate is not the reason, so NO reason
    # is stamped (only the criterion<->story gate leaves a corrective reason).
    d = swap_gate(_swap("sankey material flow", conf=0.1), **_BASE, story="voltage harmonic distortion")
    assert d["origin"] == "kept" and "gate_reject" not in d


# ── flag ON end-to-end: build.run_card re-emits ONCE with the reason, then re-gates ────────────────
def _routable_slot():
    """(page_key, card_id, target_id) for the first routable page whose card yields a swap pool."""
    from config.available_pages import available_page_keys
    from layer2.swap import candidates

    def _tmpl(pk):
        return [int(x[0]) for x in q("cmd_catalog",
                f"SELECT card_id FROM page_layout_cards WHERE page_key=$a${pk}$a$ AND card_id IS NOT NULL") if x and x[0]]
    for pk in available_page_keys():
        tpl = _tmpl(pk)
        for cid in tpl:
            pool = candidates.pool(cid, pk, tpl)
            if pool:
                return pk, cid, pool[0]["card_id"]
    return None


def test_on_build_reemits_once_with_reason(monkeypatch):
    import layer2.build as build
    slot = _routable_slot()
    assert slot, "no routable page yields a swap pool — cannot exercise the corrective re-emit"
    pk, cid, tgt = slot
    _enable(monkeypatch)                                    # gate ON for the whole run (decide.gate reads it live)
    story_angle = "hourly energy consumption trend"
    off_criterion = "sankey material flow layout"
    expected = gate_criterion_story.reject_reason({"criterion": off_criterion}, story_angle)
    calls = []

    def fake_emit(ci, feedback=None):
        calls.append({"card_id": ci["card_id"], "feedback": feedback})
        if len(calls) == 1:                                # pass 1: AI swap with an OFF-ANGLE criterion → gate rejects
            return {"swap_decision": {"action": "swap", "swap_to_id": tgt, "confidence": 0.99,
                                      "criterion": off_criterion},
                    "exact_metadata": {"k": "orig"}, "data_instructions": {"fields": []}}
        return {"swap_decision": {"action": "keep"},        # corrective re-emit (+ any finalize retry): a safe KEEP
                "exact_metadata": {"k": "orig"}, "data_instructions": {"fields": []}}

    monkeypatch.setattr(build, "emit", fake_emit)
    l1a = {"page_key": pk, "story": "", "metric": "energy", "intent": "monitor",
           "cards": [{"card_id": cid, "title": "t", "analytical_story": story_angle, "role_in_story": "lead"}],
           "interdependency_groups": []}
    l1b = {"asset": None, "column_basket": {"tables": [], "columns": []}}
    out = build.run_card("t-run", cid, l1a, l1b)
    assert calls[0]["feedback"] is None                     # first emit carries no feedback
    assert calls[1]["feedback"] == [expected]               # the ONE corrective re-emit carries the exact gate reason
    sw = out["swap_decision"]
    assert sw.get("_criterion_retry") is True               # telemetry stamped
    assert sw["action"] == "keep" and "gate_reject" not in sw   # re-gated to a safe KEEP, reason popped
    assert out["card_id"] == cid                            # no swap target → finalized against the original card
