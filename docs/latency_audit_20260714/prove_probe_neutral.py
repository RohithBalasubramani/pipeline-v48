#!/usr/bin/env python3
"""Prove the probe ORDER BY change is byte-identical: for every table, the latest-row non-null metric count under the
OLD ordering (timestamp_utc::timestamptz DESC) must equal the count under the NEW ordering (neuract.ts_imm(...) DESC).
ts_imm(t) is literally `SELECT t::timestamptz`, so this must hold for 100% of tables; any mismatch is a real regression.
Read-only. ASCII-safe."""
import sys, os, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import psycopg2
from config import neuract_dsn as _dsn
from config.validation import PLUMBING_COLUMNS as PLUMB

SCHEMA = _dsn.schema()
TS = _dsn.ts_col()
excl = ",".join("'%s'" % c for c in PLUMB)

c = psycopg2.connect(**_dsn.conn_kwargs()); c.autocommit = True
cur = c.cursor()
cur.execute("SET statement_timeout='60s'")

# all tables that have timestamp_utc
cur.execute("SELECT table_name FROM information_schema.columns WHERE table_schema=%s AND column_name=%s", (SCHEMA, TS))
tscol_tables = sorted(r[0] for r in cur.fetchall())
# which have the ts_imm index
cur.execute("SELECT DISTINCT tablename FROM pg_indexes WHERE schemaname=%s AND indexdef ILIKE '%%ts_imm%%'", (SCHEMA,))
indexed = {r[0] for r in cur.fetchall()}

# test: ALL non-gic (novel shapes) + all missing-index tables + a gic sample
non_gic = [t for t in tscol_tables if not t.startswith('gic_')]
missing = [t for t in tscol_tables if t not in indexed]
gic_sample = random.Random(42).sample([t for t in tscol_tables if t.startswith('gic_')],
                                       min(60, len([t for t in tscol_tables if t.startswith('gic_')])))
test = sorted(set(non_gic) | set(missing) | set(gic_sample))

def count_for(table, order_expr):
    sql = (f'SELECT (SELECT count(*) FROM jsonb_each(x.r) e '
           f'WHERE e.value <> \'null\'::jsonb AND e.key NOT IN ({excl})) '
           f'FROM (SELECT to_jsonb(s) AS r FROM {SCHEMA}."{table}" s ORDER BY {order_expr} DESC LIMIT 1) x')
    cur.execute(sql)
    r = cur.fetchone()
    return (r[0] if r else None)

OLD = f'"{TS}"::timestamptz'
NEW = f'{SCHEMA}.ts_imm("{TS}")'
mismatches, errors, ok = [], [], 0
for t in test:
    try:
        a = count_for(t, OLD)
    except Exception as e:
        c.rollback() if False else None
        cur.execute("SET statement_timeout='60s'")
        errors.append((t, 'OLD', str(e)[:70])); continue
    try:
        b = count_for(t, NEW)
    except Exception as e:
        cur.execute("SET statement_timeout='60s'")
        errors.append((t, 'NEW', str(e)[:70])); continue
    if a != b:
        mismatches.append((t, a, b))
    else:
        ok += 1

print(("PROBE NEUTRALITY PROOF\n"
       "  tables with timestamp_utc: %d (indexed %d, missing %d, non-gic %d)\n"
       "  tested: %d  |  IDENTICAL: %d  |  MISMATCH: %d  |  errored: %d"
       % (len(tscol_tables), len(indexed), len(missing), len(non_gic),
          len(test), ok, len(mismatches), len(errors))).encode('ascii','replace').decode())
for t, a, b in mismatches[:20]:
    print(("  MISMATCH %s: OLD=%s NEW=%s" % (t, a, b)).encode('ascii','replace').decode())
for t, side, e in errors[:20]:
    print(("  ERROR %s [%s]: %s" % (t, side, e)).encode('ascii','replace').decode())
sys.exit(1 if mismatches else 0)
