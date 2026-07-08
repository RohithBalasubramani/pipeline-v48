"""ems_exec/data/neuract.py — the ONLY door to the live NEURACT time-series (per-device gic_* tables).

Single concern: read a resolved asset TABLE by `timestamp_utc` — latest row, window endpoints, or a bucketed series.
The gic_* tables are ONE meter per table (~70 electrical cols, `timestamp_utc` text, NO `panel_id`, NO `ts`), so every
read is: filter by time only (no panel_id), request ONLY the columns that physically exist (introspect the table and
DROP the rest — a missing column is padded → None, never a SQL crash), order by `timestamp_utc` cast to timestamptz.

DB-driven: the DSN + ts column/cast come from config/neuract_dsn.py (a cmd_catalog knob with a code-default fallback).
Honest-degrade: a missing table / empty table / dropped column → {} or None, NEVER a fabricated value.
Pooled psycopg2 connections (a tiny process pool keyed by conn kwargs) so repeated per-card reads don't reconnect.

PER-CARD ONLY — this module does NOT know about panels, membership, or fan-out (retired for now). It reads ONE table.
[atomic; DB-driven; honest-degrade — reuses the neuract read semantics of layer3/apply.py, but self-contained]
"""
from __future__ import annotations

import threading

from config import neuract_dsn as _dsn

# ── a tiny connection pool (thread-safe), keyed by the frozen conn kwargs so a DSN edit gets a fresh pool ─────────────
_LOCK = threading.Lock()
_POOL: dict = {}          # key -> psycopg2 connection
_COLS_CACHE: dict = {}    # table -> frozenset(present columns)  (schema is stable per process)
_LOGGED_CACHE: dict = {}  # (table, col) -> bool: does this present column carry ANY non-null value? (reason-channel)


def _key():
    kw = _dsn.conn_kwargs()
    return tuple(sorted((k, str(v)) for k, v in kw.items()))


def _conn():
    """A live psycopg2 connection to neuract from the pool (reconnect if the pooled one died). None on any failure."""
    import psycopg2
    key = _key()
    with _LOCK:
        c = _POOL.get(key)
        if c is not None and not getattr(c, "closed", 1):
            return c
        try:
            c = psycopg2.connect(**_dsn.conn_kwargs())
            c.autocommit = True
            _POOL[key] = c
            return c
        except Exception:
            return None


def _run(sql, params=None):
    """Execute a read; return list-of-tuples (or [] on any error / dead connection — honest-degrade, never raise)."""
    c = _conn()
    if c is None:
        return []
    try:
        with c.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.fetchall()
    except Exception:
        # a broken pooled connection → drop it so the next call reconnects; the read honest-degrades to empty
        with _LOCK:
            try:
                _POOL.pop(_key(), None)
            except Exception:
                pass
        return []


# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#  column introspection — only-existing columns (a gic_* table has ~70 of the ~72 canonical cols; the rest are absent)
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
def present_columns(table):
    """The frozenset of columns that PHYSICALLY exist on `table` (cached per process). {} on error / missing table."""
    if not table:
        return frozenset()
    hit = _COLS_CACHE.get(table)
    if hit is not None:
        return hit
    rows = _run(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = %s AND table_name = %s",
        (_dsn.schema(), table),
    )
    cols = frozenset(r[0] for r in rows)
    _COLS_CACHE[table] = cols
    return cols


def column_logged(table, col):
    """Does `col` carry ANY non-null value on `table`? The reason channel's honesty check: a present column that is
    100% NULL is genuinely 'not logged by this meter' (structurally_null); a present column with real rows — even if the
    current window/latest read blanked (idle 0.0 clamped, empty window) — IS logged, so the not-logged sentence must
    NOT fire for it (F7: never claim a live column is unlogged). Cached per (table, col). False on any error / a column
    absent from the schema (the caller has already decided column_absent for those)."""
    if not table or not col or col not in present_columns(table):
        return False
    key = (table, col)
    hit = _LOGGED_CACHE.get(key)
    if hit is not None:
        return hit
    rows = _run(f'SELECT 1 FROM {_qtbl(table)} WHERE {_qcol(col)} IS NOT NULL LIMIT 1')
    logged = bool(rows)
    _LOGGED_CACHE[key] = logged
    return logged


def _existing(table, columns):
    """Split the requested columns into (present, missing) against the real table — so we only ever SELECT real ones."""
    present = present_columns(table)
    want = [c for c in (columns or []) if c]
    got = [c for c in want if c in present]
    missing = [c for c in want if c not in present]
    return got, missing


def _num(x):
    """Coerce a fetched cell to a float, else keep it (None stays None; non-numeric text passes through untouched)."""
    if x in (None, "", "NULL"):
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return x


def _qtbl(table):
    """A safely-quoted schema.table identifier (table name is a resolved DB identifier, quoted defensively)."""
    t = str(table).replace('"', '""')
    s = str(_dsn.schema()).replace('"', '""')
    return f'"{s}"."{t}"'


def _qcol(col):
    return '"' + str(col).replace('"', '""') + '"'


def _tsexpr():
    """The order/time expression: the ts column cast for time math (neuract stores ISO text → ::timestamptz)."""
    return f'{_qcol(_dsn.ts_col())}{_dsn.ts_cast()}'


# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#  latest — the newest row's {column: value} for the requested present columns (missing cols padded → None)
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
def latest(table, columns):
    """The latest (newest timestamp_utc) row as {column: value} for the requested columns. Only existing columns are
    read; every requested-but-absent column is padded → None. {} if the table is empty / missing / unreadable."""
    got, missing = _existing(table, columns)
    if not table or not got:
        return {c: None for c in (columns or []) if c}
    sel = ", ".join(_qcol(c) for c in got)
    sql = f'SELECT {sel} FROM {_qtbl(table)} ORDER BY {_tsexpr()} DESC LIMIT 1'
    rows = _run(sql)
    out = {c: None for c in missing}
    if rows:
        out.update({c: _num(v) for c, v in zip(got, rows[0])})
    else:
        out.update({c: None for c in got})
    return out


# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#  latest_ts — the newest sample timestamp of a table (freshness derivation input), or None (honest-degrade)
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
def latest_ts(table):
    """The newest sample timestamp of `table` (a timezone-aware datetime from the ::timestamptz cast), or None when
    the table is empty / missing / unreadable. This is the 'newest-sample age' input the freshness derivation
    (ems_exec/executor/freshness.py) reads — a real timestamp or nothing, never a guess."""
    if not table:
        return None
    try:
        rows = _run(f'SELECT {_tsexpr()} FROM {_qtbl(table)} ORDER BY {_tsexpr()} DESC LIMIT 1')
    except Exception:
        return None
    if not rows or not rows[0] or rows[0][0] is None:
        return None
    return rows[0][0]


# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#  window — (first_row, last_row) bounding [start, end) for windowed-delta reads (counter baselines)
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
def window(table, columns, start, end):
    """(first_row, last_row) for the requested present columns, bounding the window:
        first_row = the earliest row AT/after `start` (the counter baseline at the window open),
        last_row  = the latest row AT/before `end`   (the counter at the window close).
    start / end are ISO or bare `YYYY-MM-DD` instants; either may be None (open-ended on that side → full range there).
    Only existing columns are read; absent ones pad → None. ({}, {}) if the table is empty / missing / unreadable.
    This is the baseline pair a windowed-delta derivation deltas over (honest-degrade, never a fabricated baseline)."""
    got, missing = _existing(table, columns)
    if not table or not got:
        return {}, {}
    sel = ", ".join(_qcol(c) for c in got)
    tbl = _qtbl(table)
    tsx = _tsexpr()
    pad = {c: None for c in missing}

    def _one(where, params, order):
        rows = _run(f'SELECT {sel} FROM {tbl}{where} ORDER BY {tsx} {order} LIMIT 1', params)
        if not rows:
            return {}
        r = {c: _num(v) for c, v in zip(got, rows[0])}
        r.update(pad)
        return r

    w_start, p_start = ("", ())
    if start:
        w_start, p_start = (f' WHERE {tsx} >= %s::timestamptz', (str(start),))
    first = _one(w_start, p_start, "ASC")

    w_end, p_end = ("", ())
    if end:
        w_end, p_end = (f' WHERE {tsx} <= %s::timestamptz', (str(end),))
    last = _one(w_end, p_end, "DESC")
    return first, last


# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#  series — time-ORDERED multi-column rows over [start, end) (window/series-scoped derivations: ∫power, peaks, load-factor)
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
def series(table, columns, start, end, sampling="hourly"):
    """A DOWN-SAMPLED, NULL-SKIPPING time-series spanning the WHOLE [start, end] window as [{<col>: value, ..., ts:
    datetime}], one row per time bucket (AVG of each column in the bucket), ascending. Every row carries a `ts` datetime
    (the bucket instant) so the ∫power / rate-of-change / peak-at derivations can do time math over the full window.

    WHY BUCKETED (not raw rows): a meter logs tens of thousands of rows/window with intermittent NULLs, and a raw
    LIMITed read truncates to the window START (where power may be all-NULL). date_trunc + AVG spans the whole window,
    skips NULL samples inside a bucket, and yields evenly-spaced points the trapezoid integrates cleanly. Only existing
    columns are read; [] if the table/window is empty — honest-degrade, never a fabricated point. Buckets whose every
    column is NULL are DROPPED (so ∫power never straddles a dead gap with a fabricated value)."""
    got, _missing = _existing(table, columns)
    if not table or not got:
        return []
    gran = _SAMPLING.get((sampling or "hourly").lower(), "hour")
    tsx = _tsexpr()
    bucket = f"date_trunc('{gran}', {tsx})"
    aggs = ", ".join(f"AVG({_qcol(c)}::double precision) AS {_qcol(c)}" for c in got)
    conds, params = [], []
    if start:
        conds.append(f"{tsx} >= %s::timestamptz")
        params.append(str(start))
    if end:
        conds.append(f"{tsx} <= %s::timestamptz")
        params.append(str(end))
    where = (" WHERE " + " AND ".join(conds)) if conds else ""
    sql = (f"SELECT {bucket} AS ts, {aggs} FROM {_qtbl(table)}{where} "
           f"GROUP BY ts ORDER BY ts ASC")
    rows = _run(sql, params)
    out = []
    for r in rows:
        vals = {c: _num(v) for c, v in zip(got, r[1:])}
        if all(vals[c] is None for c in got):
            continue                                        # a fully-dead bucket → dropped (no straddling a gap)
        rec = {"ts": r[0]}                                  # a datetime (psycopg2 returns the date_trunc as datetime)
        rec.update(vals)
        out.append(rec)
    return out


# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#  bucketed — a down-sampled time series of ONE column over [start, end) (history / trend leaves)
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
_SAMPLING = {"hourly": "hour", "2hour": "hour", "shift": "hour", "day": "day", "week": "week", "month": "month"}


def bucketed(table, col, start, end, sampling="hourly"):
    """A down-sampled [{t, value}] series of ONE column, avg per time bucket over [start, end), ordered ascending.
    `sampling` maps to a date_trunc granularity (hourly/2hour/shift→hour, day, week, month; default hour). Returns [] if
    the column is absent / the table is empty / unreadable — honest-degrade, never fabricated points. PER-CARD (one
    table); no fan-out. start/end are ISO or bare dates; either may be None (open-ended on that side)."""
    if not table or not col or col not in present_columns(table):
        return []
    gran = _SAMPLING.get((sampling or "hourly").lower(), "hour")
    tbl = _qtbl(table)
    tsx = _tsexpr()
    bucket = f"date_trunc('{gran}', {tsx})"
    conds, params = [], []
    if start:
        conds.append(f"{tsx} >= %s::timestamptz")
        params.append(str(start))
    if end:
        conds.append(f"{tsx} <= %s::timestamptz")
        params.append(str(end))
    where = (" WHERE " + " AND ".join(conds)) if conds else ""
    sql = (f"SELECT {bucket} AS t, AVG({_qcol(col)}::double precision) AS v "
           f"FROM {tbl}{where} GROUP BY t ORDER BY t ASC")
    rows = _run(sql, params)
    return [{"t": (r[0].isoformat() if hasattr(r[0], "isoformat") else r[0]), "value": _num(r[1])} for r in rows]


def bucketed_raw_series(table, columns, start, end, sampling="day"):
    """Per-COARSE-bucket RAW rows: `[(bucket_ts_iso, [{col: value, …}, …]), …]` ascending — every real sample of the
    requested present columns tagged with its `date_trunc(sampling)` bucket, NOT down-sampled. One row per REAL reading
    (no AVG), grouped by the coarse bucket. This is the read a per-bucket WINDOW/SERIES-scoped derivation (load factor =
    mean(|p|)/peak(|p|)) needs so each bucket's fn runs over that bucket's OWN intra-bucket distribution — an AVG-per-bucket
    read (`series`/`bucketed`) collapses the bucket to ONE point whose mean==peak (a degenerate 100 %), and the hourly-AVG
    the scalar window fn reads smooths the peak away (a per-day mean/peak over hourly-avgs reads ~96 % vs the real ~85 %).
    Only existing columns are read; a fully-NULL sample (every requested col None) is dropped. [] when the table/window is
    empty / no column exists — honest-degrade, never a fabricated bucket. PER-CARD (one table); no fan-out."""
    got, _missing = _existing(table, columns)
    if not table or not got:
        return []
    gran = _SAMPLING.get((sampling or "day").lower(), "day")
    tsx = _tsexpr()
    bucket = f"date_trunc('{gran}', {tsx})"
    sel = ", ".join(f"{_qcol(c)}::double precision AS {_qcol(c)}" for c in got)
    conds, params = [], []
    if start:
        conds.append(f"{tsx} >= %s::timestamptz")
        params.append(str(start))
    if end:
        conds.append(f"{tsx} <= %s::timestamptz")
        params.append(str(end))
    where = (" WHERE " + " AND ".join(conds)) if conds else ""
    sql = (f"SELECT {bucket} AS b, {sel} FROM {_qtbl(table)}{where} ORDER BY b ASC, {tsx} ASC")
    rows = _run(sql, params)
    out, cur_key, cur_rows = [], object(), None
    for r in rows:
        b = r[0]
        vals = {c: _num(v) for c, v in zip(got, r[1:])}
        if all(vals[c] is None for c in got):
            continue                                        # a fully-dead sample → dropped (no fabricated point)
        key = b.isoformat() if hasattr(b, "isoformat") else b
        if key != cur_key:
            cur_key, cur_rows = key, []
            out.append((key, cur_rows))
        cur_rows.append(vals)
    return [(k, rs) for k, rs in out if rs]


def edge_count(table, col, start, end):
    """The TOTAL rising-edge count of a boolean/flag column over [start, end] — counted on the RAW rows (LAG window
    function), so a register that flaps dozens of times inside one hour reports every real edge. The old approach
    (edges over the hourly-AVG bucketed series) collapsed any flapping flag to ~1: an hourly mean of a 0/1 flag is >0
    for every active hour, so consecutive buckets never de-assert and the whole day counted a single edge — the
    cards-18/20/22 '0 events vs 25-32 real edges' defect. Returns None when the column is absent / the table is
    empty/unreadable (honest-degrade); a present, quiet flag returns a REAL 0."""
    if not table or not col or col not in present_columns(table):
        return None
    tsx = _tsexpr()
    conds, params = [], []
    if start:
        conds.append(f"{tsx} >= %s::timestamptz")
        params.append(str(start))
    if end:
        conds.append(f"{tsx} <= %s::timestamptz")
        params.append(str(end))
    where = (" WHERE " + " AND ".join(conds)) if conds else ""
    sql = (f"SELECT COUNT(*) FROM ("
           f"SELECT {_qcol(col)}::double precision AS v, "
           f"LAG({_qcol(col)}::double precision) OVER (ORDER BY {tsx}) AS pv "
           f"FROM {_qtbl(table)}{where}) s "
           f"WHERE COALESCE(s.v, 0) > 0 AND COALESCE(s.pv, 0) <= 0")
    rows = _run(sql, params)
    if not rows:
        return None
    try:
        return int(rows[0][0])
    except (TypeError, ValueError, IndexError):
        return None


def bucketed_edges(table, col, start, end, sampling="hourly"):
    """A down-sampled [{t, value}] series of the PER-BUCKET rising-edge COUNT of a boolean/flag column — every real
    de-asserted→asserted crossing inside the bucket counts (LAG over the raw rows, then grouped by date_trunc), never
    one-per-active-sample and never the collapsed bucket-avg edge (see edge_count). A bucket with rows but no edge
    reports a REAL 0 (kept, so the timeline spans the window); [] when the column is absent / the table is empty
    (honest-degrade — never a fabricated bar)."""
    if not table or not col or col not in present_columns(table):
        return []
    gran = _SAMPLING.get((sampling or "hourly").lower(), "hour")
    tsx = _tsexpr()
    conds, params = [], []
    if start:
        conds.append(f"{tsx} >= %s::timestamptz")
        params.append(str(start))
    if end:
        conds.append(f"{tsx} <= %s::timestamptz")
        params.append(str(end))
    where = (" WHERE " + " AND ".join(conds)) if conds else ""
    sql = (f"SELECT t, SUM(edge) FROM ("
           f"SELECT date_trunc('{gran}', {tsx}) AS t, "
           f"CASE WHEN COALESCE({_qcol(col)}::double precision, 0) > 0 AND "
           f"COALESCE(LAG({_qcol(col)}::double precision) OVER (ORDER BY {tsx}), 0) <= 0 "
           f"THEN 1 ELSE 0 END AS edge "
           f"FROM {_qtbl(table)}{where}) s "
           f"GROUP BY t ORDER BY t ASC")
    rows = _run(sql, params)
    return [{"t": (r[0].isoformat() if hasattr(r[0], "isoformat") else r[0]), "value": _num(r[1])} for r in rows]


def bucketed_delta(table, col, start, end, sampling="day"):
    """A down-sampled [{t, value}] series of the per-bucket CONSUMED delta of a CUMULATIVE counter (e.g.
    active_energy_import_kwh) — value = max(col) − min(col) inside each bucket, clamped ≥ 0, over [start, end), ascending.
    This is the honest per-bucket ENERGY (kWh/kVArh) for an ever-rising import counter: an AVG of the counter is the
    mid-counter-reading, NOT the energy consumed in the bucket, so an energy TREND must delta, never avg. Returns [] if
    the column is absent / the table is empty (honest-degrade). PER-CARD (one table); no fan-out. A single-sample bucket
    yields 0.0 (max==min) — a real, honest zero for that bucket, kept so the trend spans the whole window."""
    if not table or not col or col not in present_columns(table):
        return []
    gran = _SAMPLING.get((sampling or "day").lower(), "day")
    tbl = _qtbl(table)
    tsx = _tsexpr()
    bucket = f"date_trunc('{gran}', {tsx})"
    conds, params = [], []
    if start:
        conds.append(f"{tsx} >= %s::timestamptz")
        params.append(str(start))
    if end:
        conds.append(f"{tsx} <= %s::timestamptz")
        params.append(str(end))
    where = (" WHERE " + " AND ".join(conds)) if conds else ""
    dv = f"MAX({_qcol(col)}::double precision) - MIN({_qcol(col)}::double precision)"
    sql = (f"SELECT {bucket} AS t, {dv} AS v "
           f"FROM {tbl}{where} GROUP BY t ORDER BY t ASC")
    rows = _run(sql, params)
    out = []
    for r in rows:
        v = _num(r[1])
        if v is not None and v < 0:
            v = 0.0                                             # a counter reset inside the bucket → honest 0, never negative
        out.append({"t": (r[0].isoformat() if hasattr(r[0], "isoformat") else r[0]), "value": v})
    return out
