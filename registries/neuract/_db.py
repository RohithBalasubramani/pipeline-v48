"""registries/neuract/_db.py — the ONE read door for the NEURACT metadata tables (framework-light, pooled, READ-ONLY).

Single concern: hand every registry accessor in this package a parameterized SELECT against the `neuract` schema and give
back list-of-dicts (or [] on any failure — honest-degrade, never raise, never fabricate). This is the metadata twin of
ems_exec/data/neuract.py (which reads the time-series gic_* tables); THIS one reads the METADATA tables (lt_mfm, the
lt_mfm_* edge tables, lt_parameter/lt_config_*, asset/asset_type, the 3d tables).

DB-driven: the connection comes solely from config/neuract_dsn.conn_kwargs() (a cmd_catalog knob with a code-default
fallback) — nothing here hard-codes a host/port/db/schema. A tiny thread-safe process pool keyed by the frozen conn
kwargs means repeated metadata reads reuse one connection; a DSN edit rotates to a fresh pool. autocommit + read-only.
[atomic; DB-driven; honest-degrade]
"""
from __future__ import annotations

from data import neuract_pool as _pool          # THE pooled psycopg2 door (D1) — lifecycle + shared schema cache


try:
    from replay import hooks as _replay_hooks                  # record/replay seam (fail-open; None → bare calls)
except Exception:
    _replay_hooks = None


def rows(sql, params=None):
    """Run a read → list-of-tuples ([] on any error / dead connection — honest-degrade, never raise).
    REPLAY SEAM [replay/hooks.py]: recorded during a traced request; tape-served during a pinned replay."""
    if _replay_hooks is None:
        return _rows_raw(sql, params)
    return _replay_hooks.db_rows(_rows_raw, "sql.reg", sql, params)


def dicts(sql, params=None):
    """Run a read → list-of-dicts keyed by the SELECT column names ([] on any error — honest-degrade, never raise).
    REPLAY SEAM: same contract as rows() (separate tape kind — different result shape)."""
    if _replay_hooks is None:
        return _dicts_raw(sql, params)
    return _replay_hooks.db_rows(_dicts_raw, "sql.regd", sql, params)


def _rows_raw(sql, params=None):
    try:
        return _pool.run_read(sql, params, readonly=True)   # the pool drops a broken conn itself (D1)
    except Exception:
        return []


def _dicts_raw(sql, params=None):
    try:
        return _pool.run_read(sql, params, readonly=True, dict_rows=True)
    except Exception:
        return []


def one(sql, params=None):
    """Run a read expecting a single row → dict (or None if no row / error — honest-degrade)."""
    got = dicts(sql, params)
    return got[0] if got else None


def present_columns(table):
    """The frozenset of columns that PHYSICALLY exist on `table` in the neuract schema — the SHARED never-cache-empty
    probe (data/neuract_pool, D1; this door's old plain-dict cache could pin an empty set on a tunnel flap — the
    member-cache-poison class, audit H2). frozenset() on error, re-probed next call."""
    return _pool.present_columns(table, rows)


def table_exists(table):
    """True if `table` exists in the neuract schema (empty tables count as existing — honest-degrade uses this)."""
    return bool(present_columns(table))
