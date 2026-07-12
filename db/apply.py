#!/usr/bin/env python3
"""db/apply.py — the lightweight migration ledger for cmd_catalog [R9, 2026-07-12 audit F2].

WHY: the ~93 db/*.sql files (schema + seed_* + fix_* + patch_*) are hand-applied by hand, and WHICH have been applied
lives only in git history + human memory — so a from-scratch cmd_catalog rebuild is undocumented and order-sensitive
(the single biggest operational risk to the "DB rows ARE the business logic" design). This records every applied file
in a `schema_migrations` ledger so a rebuild is `python db/apply.py` and re-running is a no-op.

DELIBERATELY NOT A FRAMEWORK (owner's stated taste): no DSL, no rollback, no branching. One table + apply-in-order +
record. Files apply in FILENAME ORDER (adopt NNN_ prefixes for new files to pin order; the current set is order-tolerant
except the few documented "RUN AFTER" deps, which sort correctly by their existing names). The real disaster-recovery
source of truth remains a nightly `pg_dump` of the live cmd_catalog — this runner reproduces the *declared* state.

Usage:
    python db/apply.py --status        # show applied vs pending (no changes)
    python db/apply.py --dry-run       # list what WOULD be applied, in order
    python db/apply.py                 # apply all pending .sql files, record each
    python db/apply.py --only NAME.sql # apply one file (still recorded)

Idempotent: an already-recorded file is skipped; a file whose content changed (sha differs) is re-applied and re-stamped
(every seed is itself idempotent — ON CONFLICT / IF NOT EXISTS — so re-apply is safe). .py seeders are listed but NOT
run (they self-document their own `python db/<x>.py` invocation)."""
import argparse
import hashlib
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from config.databases import CMD_CATALOG, conn_env   # noqa: E402

_LEDGER_DDL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    filename    text PRIMARY KEY,
    sha256      text NOT NULL,
    applied_at  timestamptz NOT NULL DEFAULT now()
);
"""


def _sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _conn():
    from data.db_client import pg_connect
    c = pg_connect(CMD_CATALOG)
    c.autocommit = True
    return c


def _ensure_ledger(cur):
    cur.execute(_LEDGER_DDL)


def _applied(cur):
    cur.execute("SELECT filename, sha256 FROM schema_migrations")
    return dict(cur.fetchall())


def _sql_files():
    return sorted(f for f in os.listdir(_HERE) if f.endswith(".sql"))


def _apply_one(fname):
    """Apply one .sql via psql (matches the files' own documented `psql -f` invocation, so psql meta-commands work)."""
    ce = conn_env(CMD_CATALOG)
    env = dict(os.environ, PGPASSWORD=ce.get("PGPASSWORD", ""), PGCONNECT_TIMEOUT=ce.get("PGCONNECT_TIMEOUT", "5"))
    cmd = ["psql", "-v", "ON_ERROR_STOP=1", "-U", ce["PGUSER"], "-h", ce["PGHOST"], "-p", str(ce["PGPORT"]),
           "-d", CMD_CATALOG, "-f", os.path.join(_HERE, fname)]
    r = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(f"psql failed on {fname}: {r.stderr.strip()[:500]}")
    return r.stdout


def main():
    ap = argparse.ArgumentParser(description="cmd_catalog migration ledger")
    ap.add_argument("--status", action="store_true", help="show applied vs pending, make no changes")
    ap.add_argument("--dry-run", action="store_true", help="list what would be applied, make no changes")
    ap.add_argument("--only", metavar="FILE.sql", help="apply just this one file (still recorded)")
    args = ap.parse_args()

    conn = _conn()
    cur = conn.cursor()
    _ensure_ledger(cur)
    applied = _applied(cur)
    files = [args.only] if args.only else _sql_files()

    pending = [f for f in files if applied.get(f) != _sha(os.path.join(_HERE, f))]
    py_seeders = sorted(f for f in os.listdir(_HERE) if f.endswith(".py") and f not in ("apply.py",))

    if args.status:
        print(f"cmd_catalog schema_migrations: {len(applied)} applied, {len(pending)} pending of {len(files)} .sql")
        for f in files:
            mark = "  ok " if applied.get(f) == _sha(os.path.join(_HERE, f)) else ("CHG " if f in applied else "NEW ")
            print(f"  [{mark}] {f}")
        if py_seeders:
            print(f"NOTE: {len(py_seeders)} .py seeder(s) are NOT run by this tool: {', '.join(py_seeders)}")
        return

    if not pending:
        print("nothing to apply — cmd_catalog is up to date.")
        return

    if args.dry_run:
        print(f"would apply {len(pending)} file(s), in order:")
        for f in pending:
            print(f"  {'re-apply' if f in applied else 'apply   '} {f}")
        return

    for f in pending:
        print(f"applying {f} ...", flush=True)
        _apply_one(f)
        cur.execute(
            "INSERT INTO schema_migrations (filename, sha256) VALUES (%s, %s) "
            "ON CONFLICT (filename) DO UPDATE SET sha256=EXCLUDED.sha256, applied_at=now()",
            (f, _sha(os.path.join(_HERE, f))))
    print(f"done — {len(pending)} file(s) applied and recorded.")


if __name__ == "__main__":
    main()
