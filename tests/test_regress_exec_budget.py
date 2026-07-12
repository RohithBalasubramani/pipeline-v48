"""tests/test_regress_exec_budget.py — pins host/exec_cards._run_cards' wall-clock budget (audit fix 10,
2026-07-12): the old `as_completed(futs)` had NO timeout, so the budget branch was unreachable and ONE
black-holed neuract read blocked the whole /api/run response indefinitely. Now the budget must actually fire:
finished cards complete normally, every UNFINISHED card honest-blanks as {ok:False, why:'executor budget
exceeded'}, and the straggler is ABANDONED (shutdown(wait=False)) instead of re-blocking the response.
Offline + deterministic — fill_one_card is stubbed (the slow card parks on an Event, released at teardown so
no thread outlives the test), obs stage/span are no-op'd, no sockets. [audit_prodready TC-3 / ER-8]"""
import threading
import time
from contextlib import contextmanager

import host.exec_cards as EC


class _Span:
    def set_outputs(self, **kw):
        pass


@contextmanager
def _fake_span(*a, **k):
    yield _Span()


def _l2(cids):
    return {cid: {"exact_metadata": {"title": cid}, "data_instructions": {"consumer": {}}} for cid in cids}


def _patch_obs(monkeypatch):
    monkeypatch.setattr("obs.stage.stage", lambda *a, **k: None)          # imported inside _run_cards → binds at call
    monkeypatch.setattr("obs.span.stage_span", _fake_span)                # imported inside _fill → binds at call
    monkeypatch.setattr(EC, "_special_handling_map", lambda ids: {})      # no DB probe for handling classes


def test_budget_honest_blanks_unfinished_cards(monkeypatch):
    release = threading.Event()

    def fake_fill(**kw):
        if kw["cid"] == "card-slow":
            release.wait(timeout=10)                                      # a black-holed neuract read
            return {"late": True}
        return {"filled": kw["cid"]}

    _patch_obs(monkeypatch)
    monkeypatch.setattr(EC, "fill_one_card", fake_fill)
    monkeypatch.setattr(EC, "_exec_budget_s", lambda: 0.4)                # tiny budget → the timeout branch MUST fire
    t0 = time.time()
    try:
        completed, status = EC._run_cards(_l2(["card-a", "card-b", "card-slow"]), "t_asset", run_id="pytest")
    finally:
        release.set()                                                     # let the abandoned worker exit promptly
    wall = time.time() - t0
    assert status["card-a"] == {"ok": True, "why": "ok"}
    assert status["card-b"] == {"ok": True, "why": "ok"}
    assert completed["card-a"] == {"filled": "card-a"}
    assert completed["card-b"] == {"filled": "card-b"}
    assert status["card-slow"] == {"ok": False, "why": "executor budget exceeded"}   # honest-blank, not a hang
    assert "card-slow" not in completed                                   # its payload is never a half-result
    assert wall < 5, f"budget did not fire — _run_cards blocked {wall:.1f}s on the straggler"


def test_all_cards_complete_within_budget(monkeypatch):
    _patch_obs(monkeypatch)
    monkeypatch.setattr(EC, "fill_one_card", lambda **kw: {"filled": kw["cid"]})
    monkeypatch.setattr(EC, "_exec_budget_s", lambda: 30.0)
    completed, status = EC._run_cards(_l2(["c1", "c2"]), "t_asset", run_id="pytest")
    assert set(completed) == {"c1", "c2"}                                 # healthy path: budget changes nothing
    assert all(v == {"ok": True, "why": "ok"} for v in status.values())


def test_a_raising_fill_stays_honest_per_card(monkeypatch):
    def fake_fill(**kw):
        if kw["cid"] == "bad":
            raise ValueError("boom")                                      # run_card never raises — but stay honest if it does
        return {"filled": kw["cid"]}

    _patch_obs(monkeypatch)
    monkeypatch.setattr(EC, "fill_one_card", fake_fill)
    monkeypatch.setattr(EC, "_exec_budget_s", lambda: 30.0)
    completed, status = EC._run_cards(_l2(["good", "bad"]), "t_asset", run_id="pytest")
    assert status["good"] == {"ok": True, "why": "ok"}
    assert status["bad"]["ok"] is False and "boom" in status["bad"]["why"]
    assert "bad" not in completed
