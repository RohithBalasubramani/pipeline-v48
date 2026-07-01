"""Pandas-driven has-data filter (build-time).

Decides which neuract data tables actually carry rows, so the copilot never suggests an
empty / never-wired feeder. One batched EXISTS query per chunk -> a pandas DataFrame ->
the set of live tables. Chunked so a single bad table name can't void the whole check;
on error a chunk is kept (fail-open — better to over-suggest than silently drop real assets).
"""
import pandas as pd

import db
from config import DATA_DB, MAP_SCHEMA


def tables_with_data(tables, chunk=60):
    """Subset of `tables` (neuract table names) that have >= 1 row."""
    tables = [t for t in tables if t]
    if not tables:
        return set()
    live = set()
    for i in range(0, len(tables), chunk):
        part = tables[i:i + chunk]
        try:
            union = " UNION ALL ".join(
                f"SELECT '{t}'::text AS tbl, EXISTS(SELECT 1 FROM {MAP_SCHEMA}.\"{t}\") AS has_data"
                for t in part)
            df = pd.DataFrame(db.rows(DATA_DB, union, timeout=120), columns=["tbl", "has_data"])
            df["has_data"] = df["has_data"].astype(str).str.strip().str.lower().isin(("t", "true", "1"))
            live |= set(df.loc[df["has_data"], "tbl"])
        except Exception as e:
            print(f"  [has_data] chunk failed ({str(e)[:80]}) — keeping {len(part)} assets in it")
            live |= set(part)
    return live
