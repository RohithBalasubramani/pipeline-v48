"""tests/test_has_data_outage.py — the outage-vs-bad-chunk split in the data-layer value probes (home: data/value_probe.py; layer1b re-exports). [render-guarantee I2]

A CONNECTION/transport failure (tunnel :5433 down) must RAISE out of value_counts/tables_with_data — fail-opening every
chunk would fabricate has_data=True for the whole registry and send the run to the ambiguous picker instead of the
honest data_unavailable terminal (the exact test_render_guarantee_under_outage failure). A NON-outage error (ghost
table, SQL logic) keeps the historical fail-open: one bad chunk must not drop real assets. Fingerprints live in the ONE
home (data/outage.py; run/degrade_gate re-exports); this file pins the split without needing the live DB in any particular state. Non-live."""
from __future__ import annotations

import pytest

import data.value_probe as H


def _fresh(tables):
    """distinct table-set per test so the module caches (keyed by frozenset) can never leak between cases."""
    return list(tables)


def test_outage_error_raises_out_of_value_counts(monkeypatch):
    def dead_q(db, sql):
        raise RuntimeError('DB error (target_version1): psql: error: connection to server at "127.0.0.1", '
                           'port 5433 failed: Connection refused')
    monkeypatch.setattr(H, "q", dead_q)
    with pytest.raises(RuntimeError, match="Connection refused"):
        H.value_counts(_fresh(["t_outage_a", "t_outage_b"]))
    with pytest.raises(RuntimeError, match="Connection refused"):
        H.tables_with_data(_fresh(["t_outage_c"]))


def test_outage_result_is_never_cached(monkeypatch):
    tables = _fresh(["t_nocache_a"])
    def dead_q(db, sql):
        raise RuntimeError("server closed the connection unexpectedly")
    monkeypatch.setattr(H, "q", dead_q)
    with pytest.raises(RuntimeError):
        H.value_counts(tables)
    # the DB comes back → the SAME table set must re-probe (no fabricated entry left in the cache)
    monkeypatch.setattr(H, "q", lambda db, sql: [["t_nocache_a", "5"]])
    assert H.value_counts(tables) == {"t_nocache_a": 5}


def test_non_outage_error_keeps_fail_open(monkeypatch):
    def bad_table_q(db, sql):
        raise RuntimeError('relation "neuract.t_ghost" does not exist')
    monkeypatch.setattr(H, "q", bad_table_q)
    counts = H.value_counts(_fresh(["t_ghost", "t_real"]))
    assert counts == {"t_ghost": H.VALUE_MIN, "t_real": H.VALUE_MIN}   # kept data-bearing (historical fail-open)
    assert H.tables_with_data(_fresh(["t_ghost2"])) == {"t_ghost2"}


# --- TYPE-first triage (data/outage.py is_outage_exc): the exception TYPE decides, no fingerprint dependence ------

def test_psycopg2_operational_error_with_novel_wording_is_outage(monkeypatch):
    psycopg2 = pytest.importorskip("psycopg2")
    def dead_q(db, sql):
        raise psycopg2.OperationalError("SSL SYSCALL something brand new")   # wording matches NO fingerprint
    monkeypatch.setattr(H, "q", dead_q)
    with pytest.raises(psycopg2.OperationalError, match="brand new"):
        H.value_counts(_fresh(["t_typed_a", "t_typed_b"]))
    with pytest.raises(psycopg2.OperationalError, match="brand new"):
        H.tables_with_data(_fresh(["t_typed_c"]))


def test_connection_refused_error_type_is_outage(monkeypatch):
    def dead_q(db, sql):
        raise ConnectionRefusedError("totally unfingerprinted wording")     # ConnectionError subclass => outage by type
    monkeypatch.setattr(H, "q", dead_q)
    with pytest.raises(ConnectionRefusedError):
        H.value_counts(_fresh(["t_connref_a"]))
    with pytest.raises(ConnectionRefusedError):
        H.tables_with_data(_fresh(["t_connref_b"]))


def test_file_not_found_stays_non_outage_fail_open(monkeypatch):
    # FileNotFoundError is an OSError subclass but a LOGIC bug -- must keep the historical fail-open, never
    # be absorbed as an honest outage (the bare-OSError trap is_outage_exc's docstring forbids).
    def dead_q(db, sql):
        raise FileNotFoundError("psql binary vanished")
    monkeypatch.setattr(H, "q", dead_q)
    counts = H.value_counts(_fresh(["t_fnf_a", "t_fnf_b"]))
    assert counts == {"t_fnf_a": H.VALUE_MIN, "t_fnf_b": H.VALUE_MIN}
    assert H.tables_with_data(_fresh(["t_fnf_c"])) == {"t_fnf_c"}


def test_runtime_relation_missing_stays_non_outage_fail_open(monkeypatch):
    def bad_table_q(db, sql):
        raise RuntimeError("relation does not exist")
    monkeypatch.setattr(H, "q", bad_table_q)
    counts = H.value_counts(_fresh(["t_rel_a"]))
    assert counts == {"t_rel_a": H.VALUE_MIN}
    assert H.tables_with_data(_fresh(["t_rel_b"])) == {"t_rel_b"}


# --- libpq wire-desync family (audit 2026-07-14, 01 F2): the tunnel died MID-QUERY, so libpq mis-parses the ---------
# truncated response stream. These wordings are transport failures (engine-independent) and MUST fingerprint as
# outages so the degrade gate fires the honest data_unavailable terminal instead of a fail-open zero-validation run.

def test_libpq_desync_wordings_are_outages():
    from data.outage import is_outage_error
    assert is_outage_error("lost synchronization with server: got message type Z, length 847842554")
    assert is_outage_error('unexpected field count in "D" message')
    assert is_outage_error('Execution failed on sql \'SELECT "timestamp_utc" ... LIMIT 500\': '
                           'insufficient data in "D" message')
    # the logic-error split stays intact: missing relation is NOT an outage
    assert not is_outage_error('relation "neuract.t_ghost" does not exist')


def test_desync_wording_raises_out_of_value_counts(monkeypatch):
    def desync_q(db, sql):
        raise RuntimeError("DB error (target_version1): lost synchronization with server: got message type Z")
    monkeypatch.setattr(H, "q", desync_q)
    with pytest.raises(RuntimeError, match="lost synchronization"):
        H.value_counts(_fresh(["t_desync_a"]))
    with pytest.raises(RuntimeError, match="lost synchronization"):
        H.tables_with_data(_fresh(["t_desync_b"]))
