"""tests/test_regress_llm_admission.py — pins llm/client.py's global vLLM admission control (audit fix 11,
2026-07-12): the DB knob llm.global_concurrency DEFAULTS to 0 = DISABLED (byte-identical behavior until an
operator sets it), the disabled sentinel RE-RESOLVES per call (a cfg fail-open blip must not pin 'disabled'
for the process life), a positive cap BOUNDS total in-flight wire calls across threads, and admission waiting
is FAIL-OPEN (no slot within llm.admission_wait_s → the call proceeds; the never-acquired slot is never
over-released). Offline + deterministic — the provider wire call, cfg reader and llm_tap are all faked; no
sockets. [audit_prodready TC-3]"""
import threading
import time

import llm.client as LC


class _FakeTap:
    def record(self, **kw):
        pass

    def mark_failure(self, *a, **k):
        pass

    def clear_decision(self):
        pass


class _Provider:
    """Counts concurrent complete() calls — the seam the admission semaphore must bound."""

    def __init__(self, hold_s=0.0):
        self._lock = threading.Lock()
        self.in_flight = 0
        self.max_in_flight = 0
        self.calls = 0
        self.hold_s = hold_s

    def complete(self, system, user, **kw):
        with self._lock:
            self.in_flight += 1
            self.calls += 1
            self.max_in_flight = max(self.max_in_flight, self.in_flight)
        if self.hold_s:
            time.sleep(self.hold_s)
        with self._lock:
            self.in_flight -= 1
        return {"text": '{"ok": true}', "finish_reason": "stop", "usage": {}}


class _Providers:
    def __init__(self, p):
        self._p = p

    def resolve(self):
        return self._p


def _cfg_factory(overrides):
    return lambda key, default=None: overrides.get(key, default)


def _wire(monkeypatch, prov, cfg_overrides):
    monkeypatch.setattr(LC, "_providers", _Providers(prov))
    monkeypatch.setattr(LC, "llm_tap", _FakeTap())
    monkeypatch.setattr(LC, "_ADMISSION", None)                  # fresh resolution per test; restored on teardown
    monkeypatch.setattr(LC, "_cfg", _cfg_factory(cfg_overrides))


def test_default_zero_is_disabled_and_reresolves_per_call(monkeypatch):
    prov = _Provider()
    _wire(monkeypatch, prov, {})                                 # no row → code default 0 → disabled
    assert LC._admission_sem() is False
    assert LC._call_qwen_raw("sys", "user", stage="regress") == {"ok": True}   # disabled path: no acquire, call runs
    assert prov.calls == 1
    # only the False→semaphore transition exists: an operator flipping the knob takes effect on the NEXT call
    monkeypatch.setattr(LC, "_cfg", _cfg_factory({"llm.global_concurrency": 2}))
    sem = LC._admission_sem()
    assert isinstance(sem, threading.BoundedSemaphore) and sem._value == 2
    assert LC._admission_sem() is sem                            # a live semaphore is never replaced


def test_positive_cap_bounds_concurrent_wire_calls(monkeypatch):
    prov = _Provider(hold_s=0.15)
    _wire(monkeypatch, prov, {"llm.global_concurrency": 1, "llm.admission_wait_s": 10})
    results = []

    def worker():
        results.append(LC._call_qwen_raw("sys", "user", stage="regress"))

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert results == [{"ok": True}] * 4                         # every call completes (bounded, not dropped)
    assert prov.calls == 4
    assert prov.max_in_flight == 1, f"cap=1 but {prov.max_in_flight} wire calls overlapped"


def test_admission_wait_fails_open_without_over_release(monkeypatch):
    prov = _Provider()
    _wire(monkeypatch, prov, {"llm.global_concurrency": 1, "llm.admission_wait_s": 0.05})
    sem = LC._admission_sem()
    assert sem is not False
    assert sem.acquire(timeout=1)                                # hostage: the only slot is held for the whole test
    try:
        out = LC._call_qwen_raw("sys", "user", stage="regress")
        assert out == {"ok": True}                               # back-pressure never becomes an outage (fail-open)
        assert prov.calls == 1
        assert sem._value == 0                                   # the never-acquired slot was NOT released
    finally:
        sem.release()                                            # BoundedSemaphore raises here if the code over-released


def test_admission_rows_agree_when_present():
    """DB-row agreement [audit 05 F2]: back-pressure must never become an outage — the admission wait has to be
    strictly under the l2_emit timeout, and the cap non-negative. Skips offline (rows unreadable)."""
    from config.app_config import cfg
    cap = cfg("llm.global_concurrency", None)
    if cap is None:
        import pytest
        pytest.skip("cmd_catalog unreachable / row absent")
    assert int(cap) >= 0
    wait = float(cfg("llm.admission_wait_s", 60) or 60)
    assert wait > 0
    # NOTE deliberately NOT pinned: wait < timeout.l2_emit. Acquisition is FAIL-OPEN (a starved waiter proceeds),
    # so a wait above the emit timeout is an operator throughput choice (set 300 on 2026-07-15), not an outage risk.
