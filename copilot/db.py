"""Read-only Postgres access for the copilot, via the `psql` CLI.

Deliberately a tiny self-contained helper (NOT imported from the pipeline's
column_resolve.q / l6.db) so this layer has zero code-edge into L1/L2/L3.
All access is SELECT-only.
"""
import csv
import io
import os
import subprocess

from config import DATA_DB, DATA_HOST, DATA_PORT, PG_USER


def rows(db: str, sql: str, timeout: float = 60.0):
    """Run a SELECT and return a list of rows (each a list of str cells).

    Uses `psql --csv -t` so commas/newlines inside text columns are handled by
    the csv parser. Raises RuntimeError on psql failure. The live logging DB
    (DATA_DB) is reached on the 127.0.0.1:5433 tunnel; everything else on the
    default local socket (:5432).
    """
    cmd = ["psql", "-U", PG_USER, "-d", db]
    if db == DATA_DB:
        cmd += ["-h", DATA_HOST, "-p", str(DATA_PORT)]
    cmd += ["--csv", "-t", "-c", sql]
    env = dict(os.environ, PGCLIENTENCODING="UTF8")
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"psql {db} failed: {proc.stderr.strip()[:400]}")
    out = [r for r in csv.reader(io.StringIO(proc.stdout)) if any(c.strip() for c in r)]
    return out
