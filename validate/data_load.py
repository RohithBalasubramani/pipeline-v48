"""validate/data_load.py — load an asset's recent rows into pandas (non-AI). Reads the live neuract data tables
(`<CONSUMER_SCHEMA>.gic_*` in DATA_DB on the :5433 tunnel) — the ONE remaining live-data read of the validation pass
(registry metadata is mirror-local). [validate]"""
import pandas as pd

from config.databases import DATA_DB, CONSUMER_SCHEMA, DATA_TS_CAST
from config.validation import TIME_COLUMN, PROBE_ROWS
from data.db_client import pg_connect                                # routed connection (tunnel 5433), not local socket
from layer1b.basket.col_dict import real_table_cols


try:
    from replay import hooks as _replay_hooks                  # record/replay seam (fail-open; None → bare calls)
except Exception:
    _replay_hooks = None


def load_asset_frame(table, columns, *, limit=PROBE_ROWS):
    """The public probe — semantics in _load_asset_frame_raw. REPLAY SEAM [replay/hooks.py]: the (DataFrame, cols,
    ordered) result is recorded during a traced request and reconstructed from the tape during a pinned replay, so
    validation reproduces without the :5433 tunnel."""
    if _replay_hooks is None:
        return _load_asset_frame_raw(table, columns, limit=limit)
    return _replay_hooks.frame_probe(_load_asset_frame_raw, table, columns, limit)


def _load_asset_frame_raw(table, columns, *, limit=PROBE_ROWS):
    """Return (DataFrame, loaded_columns, ordered). Selects TIME_COLUMN + the real basket columns, newest first.
    ORDER BY casts the ISO-8601 TEXT timestamp (DATA_TS_CAST) — a plain text sort is chronological only within ONE
    tz offset, and neuract mixes +00:00/+05:30 (the latent sibling of the stale-'ts' bug). `ordered` tells the
    caller whether row 0 is genuinely the newest (False on a table with no time column)."""
    real = real_table_cols(table)                                  # guard: only columns that exist on this meter
    cols = [c for c in columns if c in real]
    ordered = TIME_COLUMN in real
    sel = [TIME_COLUMN] + cols if ordered else cols
    if not sel:
        return pd.DataFrame(), [], False
    quoted = ", ".join(f'"{c}"' for c in sel)
    qual = f'{CONSUMER_SCHEMA}."{table}"'                           # schema-qualified (search_path-free)
    sql = (f'SELECT {quoted} FROM {qual} ORDER BY "{TIME_COLUMN}"{DATA_TS_CAST} DESC LIMIT {int(limit)}'
           if ordered else f'SELECT {quoted} FROM {qual} LIMIT {int(limit)}')
    conn = pg_connect(DATA_DB)                                      # → 5433 tunnel where the neuract gic tables live
    try:
        df = pd.read_sql(sql, conn)
    finally:
        conn.close()
    return df, cols, ordered
