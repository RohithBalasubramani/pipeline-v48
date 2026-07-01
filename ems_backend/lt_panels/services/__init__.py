"""External-DB query helpers for the lt_panels app.

Each MFM holds a ``db_link`` (libpq-compatible connection string) and a
``table_name`` for the timeseries table. These helpers open a short-lived
pooled psycopg connection per request and read the latest row or a time range.

We never write or store values in Django; this package is a pure broker.

Timezone contract
-----------------
Every connection runs `SET TIME ZONE 'UTC'` immediately after opening,
so any naïve datetime the driver returns is in UTC. Combined with the
`_to_dt` check in `consumers/_base.py` (which rejects naïve datetimes),
this gives consistent rolling-window math regardless of the server's
local TZ or the column being `TIMESTAMPTZ` vs `TIMESTAMP`.

This is a barrel package: the implementation is split into single-purpose
sub-modules (config / connection / columns / timeutils / fetch_rows /
fetch_buckets / fetch_events). Importing ``from ...services import X`` keeps
working exactly as it did against the old monolith module.
"""

# ── Config / shared constants ──────────────────────────────────────────────
from .config import (
    DATA_TS_COL,
    DATA_TS_CAST,
    DATA_HAS_PANEL_ID,
    _TSQ,
    _PANEL_POS,
    _PANEL_NAMED,
    LOCAL_TZ,
    _LOCAL_TZ_NAME,
)

# ── Connection pool + row mapping ──────────────────────────────────────────
from .connection import (
    _configure_connection,
    _get_pool,
    _connect,
    _row_to_dict,
    _POOLS,
    _POOLS_LOCK,
    _POOL_MIN_SIZE,
    _POOL_MAX_SIZE,
    _POOL_TIMEOUT_SEC,
)

# ── Column introspection + list helpers ────────────────────────────────────
from .columns import (
    get_table_columns,
    invalidate_table_columns,
    _select_existing,
    _pad_missing,
    _columns_in_expr,
    _TABLE_COLUMNS_CACHE,
    _VALID_BOOL_COL,
)

# ── Time-window resolution + bucket expressions ────────────────────────────
from .timeutils import (
    _now,
    VALID_SAMPLINGS,
    _bucket_expr,
    _local_midnight,
    _parse_boundary,
    resolve_range,
)

# ── Row / window fetchers ──────────────────────────────────────────────────
from .fetch_rows import (
    fetch_live,
    fetch_config_row,
    fetch_window,
    fetch_history,
)

# ── Bucketed aggregation + energy delta ────────────────────────────────────
from .fetch_buckets import (
    fetch_bucketed,
    fetch_energy_delta,
)

# ── Boolean event-flag fetchers ────────────────────────────────────────────
from .fetch_events import (
    fetch_bool_event_counts_per_bucket,
    fetch_bool_event_records,
    fetch_bool_event_combo_per_bucket,
    fetch_bool_event_combo_records,
)


__all__ = [
    # config / constants
    'DATA_TS_COL', 'DATA_TS_CAST', 'DATA_HAS_PANEL_ID',
    'LOCAL_TZ',
    # connection
    '_connect', '_get_pool', '_row_to_dict',
    # columns
    'get_table_columns', 'invalidate_table_columns',
    # time
    '_now', 'VALID_SAMPLINGS', 'resolve_range',
    # row fetchers
    'fetch_live', 'fetch_config_row', 'fetch_window', 'fetch_history',
    # bucket / energy
    'fetch_bucketed', 'fetch_energy_delta',
    # bool events
    'fetch_bool_event_counts_per_bucket', 'fetch_bool_event_records',
    'fetch_bool_event_combo_per_bucket', 'fetch_bool_event_combo_records',
]
