"""layer1b/resolve/has_data.py — which neuract data tables actually carry usable data, so 1b never resolves/offers an
empty / never-wired / WIRED-BUT-SILENT meter. Two checks, both batched per chunk via q() (psql — stdlib, no pandas),
chunked so one bad table can't void the whole check, FAIL-OPEN, cached per process:
  · tables_with_data    — has >= 1 ROW (cheap EXISTS).
  · tables_with_values  — has >= k NON-NULL metric VALUES in its first row (a transformer with rows-but-all-null values
                          is NOT data-bearing). This is the honest has_data signal — a meter the pipeline can render.
[neuract live-data filter]"""
from data.db_client import q
from config.databases import DATA_DB, DATA_SCHEMA, DATA_TS_COL, DATA_TS_CAST
from config.validation import PLUMBING_COLUMNS as _PLUMBING   # ONE shared home with col_dict._SKIP (was drifting)

_CACHE = {}
_VAL_CACHE = {}
VALUE_MIN = 3                                          # >= this many non-null metric columns ⇒ a renderable meter


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
    counts = {t: 0 for t in tables}
    for i in range(0, len(tables), chunk):
        part = tables[i:i + chunk]
        try:
            union = " UNION ALL ".join(
                f"""SELECT '{t}'::text AS tbl, (SELECT count(*) FROM jsonb_each(x.r) e
                       WHERE e.value <> 'null'::jsonb AND e.key NOT IN ({excl})) AS n
                    FROM (SELECT to_jsonb(s) AS r FROM {DATA_SCHEMA}."{t}" s ORDER BY "{DATA_TS_COL}"{DATA_TS_CAST} DESC LIMIT 1) x"""
                for t in part)
            for r in q(DATA_DB, union):
                counts[r[0]] = int(r[1])
        except Exception as e:
            # OUTAGE ≠ bad chunk [render-guarantee I2]: a connection/transport failure means the DATA DB itself is
            # unreachable — every chunk would "fail open" and resolution would proceed on FABRICATED has_data=True
            # signals (→ ambiguous picker) instead of the honest data_unavailable terminal. Re-raise so run_1b's
            # layer-exception reaches the degrade gate (the ONE outage-fingerprint home). A NON-outage error (bad
            # table, SQL logic) keeps the fail-open: one bad chunk must not drop real assets.
            from run.degrade_gate import is_outage_error
            if is_outage_error(e):
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


def has_meaningful_data(asset, page_key=None):
    """The SHARED honest has-data gate: present ∧ non_null ∧ MEANINGFUL for `page_key`.

    Delegates to the grounding engine (grounding.meaningful — the single source of truth), which routes the asset's
    schema fingerprint, checks the page's required metric class, and probes the latest row against the EDITABLE
    data_quality_policy knobs (padded-0 / denorm garbage / all-null-THD / reversed-CT energy). `asset` is the
    asset_candidates.as_asset() dict (or a bare neuract table name); `page_key` is the routed page (None ⇒ any-metric).

    True ⇒ the meter can render real values for the page; False ⇒ the caller honest-degrades with the machine cause from
    grounding.meaningful.probe(). Import is LAZY to avoid a cycle (grounding.meaningful reuses value_counts/VALUE_MIN
    from this module). [DS-01/04/06, VC-09, has_data≠meaningful]
    """
    from grounding.meaningful import has_meaningful_data as _grounded
    try:
        return _grounded(asset, page_key)
    except Exception as e:  # fail-open to the row/value signal so a probe bug can't blanket-blank real assets
        import sys
        sys.stderr.write(f"[has_meaningful_data] probe failed ({str(e)[:80]}) — falling back to value-count\n")
        table = asset.get("table") if isinstance(asset, dict) else asset
        return bool(table) and table in tables_with_values([table])


def meaningful_probe(asset, page_key=None):
    """The full verdict dict {ok, present, non_null, meaningful, cause, fingerprint} — for callers that need the reason,
    not just the boolean (the fact-sheet reason channel). Same delegation + lazy import as has_meaningful_data."""
    from grounding.meaningful import probe
    return probe(asset, page_key)


def tables_with_data(tables, chunk=60):
    """Subset of `tables` (neuract table names) that have >= 1 row. Cached by the input table-set."""
    tables = [t for t in tables if t]
    if not tables:
        return set()
    key = frozenset(tables)
    if key in _CACHE:
        return _CACHE[key]
    live = set()
    for i in range(0, len(tables), chunk):
        part = tables[i:i + chunk]
        try:
            union = " UNION ALL ".join(
                f"""SELECT '{t}'::text AS tbl, EXISTS(SELECT 1 FROM {DATA_SCHEMA}."{t}") AS has_data"""
                for t in part)
            rows = q(DATA_DB, union)
            live |= {r[0] for r in rows if len(r) > 1 and str(r[1]).strip().lower() in ("t", "true", "1")}
        except Exception as e:
            # same outage-vs-bad-chunk split as value_counts (see above): connection failure → honest raise; a bad
            # table name keeps the fail-open so one ghost table can't drop the whole chunk's real assets.
            from run.degrade_gate import is_outage_error
            if is_outage_error(e):
                raise
            import sys
            sys.stderr.write(f"[has_data] chunk failed ({str(e)[:80]}) — keeping {len(part)} assets\n")
            live |= set(part)
    _CACHE[key] = live
    return live
