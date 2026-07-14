"""data/value_probe.py — which neuract data tables actually carry usable data. THE shared row/value probes, so no
layer ever resolves/offers an empty / never-wired / WIRED-BUT-SILENT meter. Two checks, both batched per chunk via q()
(psql — stdlib, no pandas), chunked so one bad table can't void the whole check, FAIL-OPEN, TTL-cached:
  · tables_with_data    — has >= 1 ROW (cheap EXISTS).
  · tables_with_values  — has >= k NON-NULL metric VALUES in its latest row (a transformer with rows-but-all-null
                          values is NOT data-bearing). This is the honest has_data signal — a meter the pipeline can
                          render.

Home moved from layer1b/resolve/has_data.py (which re-exports for its callers) so grounding.meaningful and
data.lt_panels can consume the probes without importing a layer — the grounding↔layer1b import cycle is dead.
[neuract live-data filter] [cycle-kill 2026-07-12]
"""
from data.db_client import q, pg_bool
from config.databases import DATA_DB, DATA_SCHEMA, DATA_TS_COL, DATA_TS_CAST
from config.neuract_dsn import ts_order_expr
from config.validation import PLUMBING_COLUMNS as _PLUMBING   # ONE shared home with col_dict._SKIP (was drifting)
from data.outage import is_outage_exc
from data.ttl_cache import TTLCache

# TTL-expiring so a transient :5433 flap that lands a stale has-data set self-heals within cache.resolution_ttl_s
# instead of poisoning the long-running server until restart [poison-permanent-fix]
_CACHE = TTLCache()
_VAL_CACHE = TTLCache()
_EXIST_CACHE = TTLCache()
VALUE_MIN = 3                                          # >= this many non-null metric columns ⇒ a renderable meter


def existing_tables(tables):
    """Subset of `tables` that physically exist in the live schema (ONE cached information_schema read).

    Registry drift is real (plant lt_mfm names ≠ schema: the gic_15 *_sch and gic_30 blocks — entry-level
    validation 2026-07-12, console_validation/sql.md): a ghost table used to fail its WHOLE probe chunk, and the
    fail-open then marked all ~40 co-batched tables data-bearing — a fabricated has_data=True for never-wired
    meters. Filtering here makes ghosts honestly read 0/no-data while real tables get real probes.
    Outage → raise (I2, same as the probes); introspection hiccup → fail-open to NO filtering (never drop real
    assets on a guard error); empty result never cached."""
    tables = [t for t in tables if t]
    if not tables:
        return []
    allset = _EXIST_CACHE["__all__"] if "__all__" in _EXIST_CACHE else None
    if allset is None:
        try:
            rows = q(DATA_DB, "SELECT table_name FROM information_schema.tables "
                              f"WHERE table_schema = '{DATA_SCHEMA}'")
            allset = {r[0] for r in rows}
        except Exception as e:
            if is_outage_exc(e):
                raise
            return tables
        if not allset:
            return tables
        _EXIST_CACHE["__all__"] = allset
    return [t for t in tables if t in allset]


def value_counts(tables, chunk=40):
    """{table: count of NON-NULL metric columns in its LATEST row}. One index-scan jsonb read per table (ORDER BY the TS
    column DESC, btree-indexed → cheap), batched + chunked. A 0-row / all-null / went-silent table gets 0. Cached."""
    tables = [t for t in tables if t]
    if not tables:
        return {}
    key = frozenset(tables)
    if key in _VAL_CACHE:
        return _VAL_CACHE[key]
    excl = ",".join(f"'{c}'" for c in _PLUMBING)
    counts = {t: 0 for t in tables}                    # ghosts (registry drift) stay 0 = honestly not data-bearing
    real = existing_tables(tables)
    for i in range(0, len(real), chunk):
        part = real[i:i + chunk]
        try:
            union = " UNION ALL ".join(
                f"""SELECT '{t}'::text AS tbl, (SELECT count(*) FROM jsonb_each(x.r) e
                       WHERE e.value <> 'null'::jsonb AND e.key NOT IN ({excl})) AS n
                    FROM (SELECT to_jsonb(s) AS r FROM {DATA_SCHEMA}."{t}" s ORDER BY {ts_order_expr(DATA_TS_COL)} DESC LIMIT 1) x"""
                for t in part)
            for r in q(DATA_DB, union):
                counts[r[0]] = int(r[1])
        except Exception as e:
            # OUTAGE ≠ bad chunk [render-guarantee I2]: a connection/transport failure means the DATA DB itself is
            # unreachable — every chunk would "fail open" and resolution would proceed on FABRICATED has_data=True
            # signals (→ ambiguous picker) instead of the honest data_unavailable terminal. Re-raise so run_1b's
            # layer-exception reaches the degrade gate. A NON-outage error (bad table, SQL logic) keeps the
            # fail-open: one bad chunk must not drop real assets.
            if is_outage_exc(e):
                raise
            import sys
            sys.stderr.write(f"[value_counts] chunk failed ({str(e)[:80]}) — keeping {len(part)} assets\n")
            for t in part:
                counts[t] = VALUE_MIN                  # treat as data-bearing on error
    _VAL_CACHE[key] = counts
    return counts


def tables_with_values(tables, k=VALUE_MIN):
    """Subset of `tables` whose LATEST row has >= k NON-NULL metric columns — the VALUE-aware has_data (vs row-existence).
    Excludes never-wired AND went-silent meters (rows present, latest values all-null). [1b: offer only renderable meters]"""
    return {t for t, n in value_counts(tables).items() if n >= k}


def tables_with_data(tables, chunk=60):
    """Subset of `tables` (neuract table names) that have >= 1 row. Cached by the input table-set."""
    tables = [t for t in tables if t]
    if not tables:
        return set()
    key = frozenset(tables)
    if key in _CACHE:
        return _CACHE[key]
    live = set()
    real = existing_tables(tables)                     # ghosts (registry drift) never probed → never "have data"
    for i in range(0, len(real), chunk):
        part = real[i:i + chunk]
        try:
            union = " UNION ALL ".join(
                f"""SELECT '{t}'::text AS tbl, EXISTS(SELECT 1 FROM {DATA_SCHEMA}."{t}") AS has_data"""
                for t in part)
            rows = q(DATA_DB, union)
            live |= {r[0] for r in rows if len(r) > 1 and pg_bool(r[1])}
        except Exception as e:
            # same outage-vs-bad-chunk split as value_counts (see above): connection failure → honest raise; a bad
            # table name keeps the fail-open so one ghost table can't drop the whole chunk's real assets.
            if is_outage_exc(e):
                raise
            import sys
            sys.stderr.write(f"[has_data] chunk failed ({str(e)[:80]}) — keeping {len(part)} assets\n")
            live |= set(part)
    _CACHE[key] = live
    return live
