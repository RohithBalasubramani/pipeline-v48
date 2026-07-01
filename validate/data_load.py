"""validate/data_load.py — load an asset's recent rows into pandas (non-AI). Reads the neuract compat views
(`<CONSUMER_SCHEMA>.cmp_mfm_*` in DATA_DB), same source as 1b's col_dict — NOT the deprecated lt_panels. [validate]"""
import pandas as pd

from config.databases import DATA_DB, CONSUMER_SCHEMA
from config.validation import TIME_COLUMN, PROBE_ROWS
from data.db_client import pg_connect                                # routed connection (tunnel 5433), not local socket
from layer1b.basket.col_dict import real_table_cols


def load_asset_frame(table, columns, *, limit=PROBE_ROWS):
    """Return (DataFrame, loaded_columns). Selects TIME_COLUMN + the real basket columns, newest first."""
    real = real_table_cols(table)                                  # guard: only columns that exist on this meter (compat)
    cols = [c for c in columns if c in real]
    sel = [TIME_COLUMN] + cols if TIME_COLUMN in real else cols
    if not sel:
        return pd.DataFrame(), []
    quoted = ", ".join(f'"{c}"' for c in sel)
    qual = f'{CONSUMER_SCHEMA}."{table}"'                           # schema-qualify the compat view (search_path-free)
    sql = f'SELECT {quoted} FROM {qual} ORDER BY "{TIME_COLUMN}" DESC LIMIT {int(limit)}' \
        if TIME_COLUMN in real else f'SELECT {quoted} FROM {qual} LIMIT {int(limit)}'
    conn = pg_connect(DATA_DB)                                      # → 5433 tunnel where the neuract gic tables live
    try:
        df = pd.read_sql(sql, conn)
    finally:
        conn.close()
    return df, cols
