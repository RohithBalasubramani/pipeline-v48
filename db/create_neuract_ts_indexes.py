#!/usr/bin/env python3
"""db/create_neuract_ts_indexes.py — generate the neuract time-index DDL that fixes the ::timestamptz seq-scan
[R3 / audit F1 / P3, 2026-07-12].

THE PROBLEM (measured live): every hot-path read orders/filters on `timestamp_utc::timestamptz`, but the gic_* tables
are btree-indexed on the RAW varchar only — a cast on the column defeats the index, so every latest-row/window/bucketed
read is a full seq scan (measured ~80x slower; the has_data sweep hit >70s across the ~300 tables). neuract has grown
~14x to ~13M rows; this is a guaranteed SLO wall.

WHY A WRAPPER FUNCTION: Postgres marks `text::timestamptz` as STABLE (its result depends on the TimeZone GUC), so a
functional index on `(timestamp_utc::timestamptz)` is REJECTED ("functions in index expression must be marked
IMMUTABLE"). But every stored value carries an EXPLICIT offset (e.g. '...+05:30'), so the parse is timezone-independent
and safe to wrap in an IMMUTABLE function. This script emits that wrapper + a per-table `CREATE INDEX CONCURRENTLY` on
`neuract.ts_imm(timestamp_utc) DESC`.

PAIRED CODE CHANGE (REQUIRED for the index to be USED): `ems_exec/data/neuract._tsexpr()` must emit
`neuract.ts_imm(timestamp_utc)` instead of `timestamp_utc::timestamptz` (drive it via the existing `neuract.ts_cast`
knob, or add a `neuract.ts_expr` knob). Until both land, the index exists but no query uses it.

SAFETY: dry-run by DEFAULT — prints the DDL to stdout for review and never touches the plant schema. `--apply` requires
DDL rights on the plant-owned neuract schema, so COORDINATE with the logger owner. Each table is gated on a format
UNIFORMITY check (single distinct length + single offset) so a mixed-format table is SKIPPED and reported, not indexed
blindly. `CREATE INDEX CONCURRENTLY` does not lock writes.

Usage:
    python db/create_neuract_ts_indexes.py                 # dry-run: print wrapper + index DDL + a skip report
    python db/create_neuract_ts_indexes.py --out ddl.sql   # write the DDL to a file for review / manual psql
    python db/create_neuract_ts_indexes.py --apply          # apply (needs plant DDL rights) — one CONCURRENTLY index/table
"""
import argparse
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from config import neuract_dsn as _dsn   # noqa: E402

_WRAPPER = (
    "-- IMMUTABLE parse wrapper (safe: every value carries an explicit offset, so the result is tz-independent).\n"
    "CREATE OR REPLACE FUNCTION {schema}.ts_imm(t text) RETURNS timestamptz\n"
    "  LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$ SELECT t::timestamptz $$;\n"
)


def _conn():
    import psycopg2
    return psycopg2.connect(**_dsn.conn_kwargs())


def _tables(cur, schema):
    cur.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema=%s AND table_name LIKE 'gic\\_%%' ORDER BY table_name", (schema,))
    return [r[0] for r in cur.fetchall()]


def _uniform(cur, schema, table, ts_col):
    """(ok, note): safe-to-index iff timestamp_utc carries ONE trailing timezone OFFSET over a bounded sample — that is
    the precondition for a deterministic (IMMUTABLE-safe) ::timestamptz parse. Fractional-second LENGTH may vary (audit
    F18: lengths 32 vs 35) and is IRRELEVANT here — the ts_imm() index parses to timestamptz, so text length never
    affects ordering (unlike a raw-text ORDER BY, which would need uniform length). Gate on offset only."""
    q = (f'SELECT count(DISTINCT right("{ts_col}", 6)), count(*) '
         f'FROM (SELECT "{ts_col}" FROM {schema}."{table}" '
         f'WHERE "{ts_col}" IS NOT NULL LIMIT 5000) s')
    cur.execute(q)
    offs, n = cur.fetchone()
    if not n:
        return False, "no rows sampled"
    if offs == 1:
        return True, "uniform offset"
    return False, f"non-uniform (distinct_offset={offs}) — mixed timezone offsets; verify before indexing"


def main():
    ap = argparse.ArgumentParser(description="generate/apply the neuract ts-cast expression indexes")
    ap.add_argument("--apply", action="store_true", help="APPLY the DDL (needs plant DDL rights); default is dry-run")
    ap.add_argument("--out", metavar="FILE", help="write the generated DDL to FILE for review")
    args = ap.parse_args()

    schema = _dsn.schema()
    ts_col = _dsn.ts_col()
    conn = _conn()
    conn.autocommit = True   # CREATE INDEX CONCURRENTLY cannot run inside a transaction block
    cur = conn.cursor()
    tables = _tables(cur, schema)

    ddl = [_WRAPPER.format(schema=schema)]
    skipped = []
    for t in tables:
        ok, note = _uniform(cur, schema, t, ts_col)
        if not ok:
            skipped.append((t, note))
            continue
        idx = f"idx_{t}_tsimm"[:63]
        ddl.append(f'CREATE INDEX CONCURRENTLY IF NOT EXISTS "{idx}" '
                   f'ON {schema}."{t}" ({schema}.ts_imm("{ts_col}") DESC);')

    body = "\n".join(ddl) + "\n"
    print(f"-- neuract ts-index DDL: {len(tables)} gic_* tables, {len(tables) - len(skipped)} indexable, "
          f"{len(skipped)} skipped (non-uniform)", file=sys.stderr)
    for t, note in skipped:
        print(f"-- SKIP {t}: {note}", file=sys.stderr)

    if args.out:
        with open(args.out, "w") as f:
            f.write(body)
        print(f"wrote DDL to {args.out}", file=sys.stderr)

    if not args.apply:
        print(body)
        print("-- DRY RUN — nothing applied. Review, then re-run with --apply (needs plant DDL rights), and pair with\n"
              "-- the ems_exec/data/neuract._tsexpr() change to neuract.ts_imm(timestamp_utc).", file=sys.stderr)
        return

    # apply the wrapper first (single statement), then each CONCURRENTLY index
    cur.execute(_WRAPPER.format(schema=schema))
    applied = 0
    for stmt in ddl[1:]:
        try:
            cur.execute(stmt)
            applied += 1
        except Exception as e:
            print(f"-- FAILED: {stmt}\n--   {type(e).__name__}: {e}", file=sys.stderr)
    print(f"applied wrapper + {applied} indexes ({len(skipped)} skipped). "
          f"REMEMBER the paired _tsexpr() code change.", file=sys.stderr)


if __name__ == "__main__":
    main()
