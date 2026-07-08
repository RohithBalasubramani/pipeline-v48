"""data/db_client.py — q(db, sql) via psql; raises on non-zero (no silent empty)."""
import csv
import io
import os
import subprocess
import sys

from config.databases import PSQL_USER, conn_env


def q(db, sql):
    out = subprocess.run(
        ["psql", "-U", PSQL_USER, "-d", db, "--csv", "-t", "-c", sql],
        capture_output=True, text=True,
        env={**os.environ, "PGCLIENTENCODING": "UTF8", **conn_env(db)},  # route db → tunnel/catalog endpoint
    )
    if out.returncode != 0:
        err = (out.stderr or "").strip()[:300]
        sys.stderr.write(f"[db error - {db}] {err}\n  SQL: {sql[:200]}\n")
        raise RuntimeError(f"DB error ({db}): {err}")
    return [r for r in csv.reader(io.StringIO(out.stdout)) if r]


def pg_connect(db):
    """A psycopg2 connection to `db`, ROUTED to the right endpoint (tunnel 5433 vs local catalog 5432) via conn_env —
    for callers that need a live cursor / pandas DataFrame (validate's data read), not q()'s subprocess rows. Without
    this, a bare psycopg2.connect(dbname=...) defaults to the local socket and misses the tunneled DATA/REGISTRY DBs."""
    import psycopg2
    ce = conn_env(db)
    return psycopg2.connect(dbname=db, user=ce["PGUSER"], host=ce["PGHOST"], port=ce["PGPORT"],
                            password=(ce["PGPASSWORD"] or None),
                            connect_timeout=int(ce.get("PGCONNECT_TIMEOUT", "5")))  # dead tunnel → fail fast, not ~2min TCP hang
