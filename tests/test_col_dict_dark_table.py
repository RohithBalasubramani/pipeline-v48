"""tests/test_col_dict_dark_table.py — the dangling-registry (dark-table) degrade in the basket samplers.

A registry row whose table_name points at NO physical relation must sample as a DARK table (empty column set →
the honest no_data/skeleton lane), never raise the uncaught "relation does not exist" that shipped a silent
ok=True 0-card page [audit 2026-07-14, 01 F1]. The split is exact:
  · missing relation → set() (dark) + once-per-table dangling_registry_table telemetry;
  · OUTAGE-shaped failure (tunnel cut mid-sample) → still RAISES so run/degrade_gate fires data_unavailable;
  · any other SQL/logic bug → still RAISES (data/outage.py mandate: logic errors stay loud).
build_basket short-circuits a sync-stamped ghost (table_exists is False) before any sample or LLM call. Non-live."""
from __future__ import annotations

import pytest

import layer1b.basket.col_dict as CD
import layer1b.basket.column_basket as CB


def _fresh_noted():
    CD._DANGLING_NOTED.clear()


def test_missing_relation_degrades_to_dark_table(monkeypatch):
    _fresh_noted()
    def dead_q(db, sql):
        if "information_schema" in sql:
            return []                              # missing table has no columns
        raise RuntimeError('DB error (target_version1): relation "neuract.gic_15_x_sch" does not exist')
    monkeypatch.setattr(CD, "q", dead_q)
    assert CD.latest_nonnull("gic_15_x_sch") == set()
    # window_nonnull falls back to latest_nonnull → same dark answer, still no raise
    assert CD.window_nonnull("gic_15_x_sch") == set()


def test_missing_relation_notes_telemetry_once_per_table(monkeypatch):
    _fresh_noted()
    seen = []
    def dead_q(db, sql):
        if "information_schema" in sql:
            return []
        raise RuntimeError('relation "neuract.gic_dark" does not exist')
    monkeypatch.setattr(CD, "q", dead_q)
    import obs.failures as F
    monkeypatch.setattr(F, "record", lambda stage, reason, **kw: seen.append((stage, reason, kw.get("detail"))))
    CD.latest_nonnull("gic_dark")
    CD.latest_nonnull("gic_dark")                  # second sample of the same table: throttled
    assert seen == [("layer1b", "dangling_registry_table", "gic_dark")]


def test_outage_during_sample_still_raises(monkeypatch):
    _fresh_noted()
    def dead_q(db, sql):
        if "information_schema" in sql:
            return []
        raise RuntimeError('psql: error: connection to server at "127.0.0.1", port 5433 failed: Connection refused')
    monkeypatch.setattr(CD, "q", dead_q)
    with pytest.raises(RuntimeError, match="Connection refused"):
        CD.latest_nonnull("gic_any")


def test_desync_outage_during_sample_still_raises(monkeypatch):
    # the libpq wire-desync family fingerprints as an outage now — must propagate to the degrade gate too
    _fresh_noted()
    def dead_q(db, sql):
        if "information_schema" in sql:
            return []
        raise RuntimeError("lost synchronization with server: got message type Z")
    monkeypatch.setattr(CD, "q", dead_q)
    with pytest.raises(RuntimeError, match="lost synchronization"):
        CD.latest_nonnull("gic_any2")


def test_other_logic_errors_stay_loud(monkeypatch):
    _fresh_noted()
    def dead_q(db, sql):
        if "information_schema" in sql:
            return []
        raise RuntimeError("syntax error at or near SELECT")
    monkeypatch.setattr(CD, "q", dead_q)
    with pytest.raises(RuntimeError, match="syntax error"):
        CD.latest_nonnull("gic_any3")


def test_build_basket_ghost_short_circuits_before_sample_and_llm(monkeypatch):
    def boom_sample(*a, **k):
        raise AssertionError("a sync-stamped ghost must never be sampled")
    monkeypatch.setattr(CB, "window_nonnull", boom_sample)
    monkeypatch.setattr(CB, "col_dict", boom_sample)
    monkeypatch.setattr(CB, "call_qwen", boom_sample, raising=False)
    out = CB.build_basket("voltage for pcc transformer 1",
                          {"table": "gic_15_x_sch", "table_exists": False, "mfm_id": 164})
    assert out == {"tables": [], "columns": [], "probable": [], "n_columns": 0, "llm_failed": False}


def test_build_basket_legacy_dict_without_key_still_samples(monkeypatch):
    # legacy asset dicts (no table_exists key) keep today's path — only an EXPLICIT False short-circuits
    called = []
    monkeypatch.setattr(CB, "window_nonnull", lambda t: called.append(t) or set())
    monkeypatch.setattr(CB, "col_dict", lambda t: [])
    monkeypatch.setattr(CB, "call_qwen", lambda *a, **k: {}, raising=False)
    CB.build_basket("x", {"table": "gic_real"})
    assert called == ["gic_real"]
