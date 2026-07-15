"""tests/test_regress_connect_retry.py — the bounded outage-shaped connect retry (data/connect_retry.py, audit 01 F3).

Pins: outage-shaped connect failures retry within the db.connect_retry_s budget then succeed; logic errors NEVER
retry; budget 0 (code default) = single attempt, byte-identical to the pre-2026-07-15 behavior; the nested
cfg-read connect passes through unretried (re-entrancy guard); the _q_pool RuntimeError normalization contract
survives an exhausted retry. Non-live (time.sleep patched)."""
from __future__ import annotations

import pytest

import data.connect_retry as CR


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(CR.time, "sleep", lambda s: None)
    yield


def _budget(monkeypatch, seconds):
    monkeypatch.setattr(CR, "_budget_s", lambda: float(seconds))


def test_outage_retries_then_succeeds(monkeypatch):
    _budget(monkeypatch, 8.0)
    attempts = []
    def connect():
        attempts.append(1)
        if len(attempts) < 3:
            raise ConnectionRefusedError("connection refused")
        return "CONN"
    assert CR.with_retry(connect, "db") == "CONN"
    assert len(attempts) == 3


def test_logic_error_never_retries(monkeypatch):
    _budget(monkeypatch, 8.0)
    attempts = []
    def connect():
        attempts.append(1)
        raise FileNotFoundError("psql binary vanished")          # OSError subclass but a LOGIC bug
    with pytest.raises(FileNotFoundError):
        CR.with_retry(connect, "db")
    assert len(attempts) == 1


def test_budget_zero_is_single_attempt(monkeypatch):
    _budget(monkeypatch, 0.0)
    attempts = []
    def connect():
        attempts.append(1)
        raise ConnectionRefusedError("refused")
    with pytest.raises(ConnectionRefusedError):
        CR.with_retry(connect, "db")
    assert len(attempts) == 1                                    # code default: byte-identical to today


def test_exhausted_budget_reraises_last(monkeypatch):
    _budget(monkeypatch, 0.0001)                                 # tiny budget: one loop at most
    def connect():
        raise TimeoutError("timeout expired")
    with pytest.raises(TimeoutError):
        CR.with_retry(connect, "db")


def test_nested_connect_never_retried(monkeypatch):
    _budget(monkeypatch, 8.0)
    inner_attempts = []
    def inner():
        inner_attempts.append(1)
        raise ConnectionRefusedError("refused-inner")
    def outer():
        # simulates the cfg read connecting from INSIDE the retry loop
        with pytest.raises(ConnectionRefusedError):
            CR.with_retry(inner, "cfg")
        return "OUTER-CONN"
    assert CR.with_retry(outer, "db") == "OUTER-CONN"
    assert len(inner_attempts) == 1                              # the nested call was a single bare attempt


def test_q_pool_normalization_contract_survives(monkeypatch):
    """_q_pool still returns the uniform RuntimeError('DB error (db): …') on an exhausted-connect failure —
    the degrade-gate fingerprint contract [audit 01 F7]."""
    import data.db_client as DC
    _budget(monkeypatch, 0.0)
    monkeypatch.setattr(DC, "pg_connect", lambda db: (_ for _ in ()).throw(
        ConnectionRefusedError('connection to server at "127.0.0.1", port 5433 failed: Connection refused')))
    monkeypatch.setattr(DC, "_POOL", {})
    with pytest.raises(RuntimeError, match=r"DB error \(testdb\).*Connection refused"):
        DC._q_pool("testdb", "SELECT 1")
