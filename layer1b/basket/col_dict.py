"""layer1b/basket/col_dict.py — the meter's metric dictionary + has-data, read from the REAL consumer view columns
(neuract via the `compat.cmp_mfm_*` views that ems_backend reads), so 1b's basket matches the live data exactly.
Replaces the stale lt_parameter dictionary (only 47/180 of its names exist in neuract). [neuract migration]"""
import json

from data.db_client import q
from config.databases import DATA_DB, CONSUMER_SCHEMA, DATA_TS_COL
from layer1b.basket.describe import describe

_SKIP = {"ts", "panel_id", "timestamp_utc"}     # contract plumbing, not metric columns


def real_table_cols(table):
    rows = q(DATA_DB, "SELECT DISTINCT column_name FROM information_schema.columns "
                      f"WHERE table_schema=$a${CONSUMER_SCHEMA}$a$ AND table_name=$a${table}$a$")
    return {r[0] for r in rows if r and r[0]}


def col_dict(table):
    """rows: [column_name, label, kind, unit] for the asset's REAL consumer columns. (Was keyed by mfm_type_id over
    lt_parameter; now reads the real cmp_mfm view — neuract is uniform + self-describing.)"""
    cols = sorted(c for c in real_table_cols(table) if c not in _SKIP)
    return [[c] + describe(c) for c in cols]


def latest_nonnull(table):
    # Order by the configured timestamp column to read the GENUINE LATEST row — neuract stores timestamp_utc as ISO-8601
    # TEXT (so the old `data_type LIKE 'timestamp%'` probe never matched → unordered LIMIT 1 → an ARBITRARY heap row, which
    # disagreed with validate and mis-flagged went-silent meters). Text sort of ISO-8601 is chronological; a btree index on
    # timestamp_utc makes DESC LIMIT 1 an index scan. Guard: only order if the column exists on this table.
    ob = f'ORDER BY "{DATA_TS_COL}" DESC' if DATA_TS_COL in real_table_cols(table) else ""
    rows = q(DATA_DB, f'SELECT to_jsonb(t) FROM {CONSUMER_SCHEMA}."{table}" t {ob} LIMIT 1')
    if not rows or not rows[0] or not rows[0][0]:
        return set()
    try:
        d = json.loads(rows[0][0])
    except Exception:
        return set()
    return {k for k, v in d.items() if v not in (None, "")}
