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
