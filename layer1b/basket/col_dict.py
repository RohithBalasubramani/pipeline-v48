"""layer1b/basket/col_dict.py — the meter's metric dictionary + has-data, read from the REAL live table columns
(`neuract.gic_*` information_schema — physical truth, includes the accumulation columns device_mappings doesn't map),
so 1b's basket matches the live data exactly. The windowed has_data here is the BASKET-AI HINT only (it runs before
validate); the authoritative per-column verdict is the pre-Layer-2 validate pass, folded back into the basket.
[neuract migration; validate-consolidation]"""
import json

from data.db_client import q
from config.databases import DATA_DB, CONSUMER_SCHEMA, DATA_TS_COL, DATA_TS_CAST
from config.neuract_dsn import ts_order_expr
from config.validation import PLUMBING_COLUMNS
from layer1b.basket.describe import describe

_SKIP = set(PLUMBING_COLUMNS)                   # contract plumbing, not metric columns (ONE shared home w/ has_data)


def real_table_cols(table):
    rows = q(DATA_DB, "SELECT DISTINCT column_name FROM information_schema.columns "
                      f"WHERE table_schema=$a${CONSUMER_SCHEMA}$a$ AND table_name=$a${table}$a$")
    return {r[0] for r in rows if r and r[0]}


def col_dict(table):
    """rows: [column_name, label, kind, unit] for the asset's REAL consumer columns. (Was keyed by mfm_type_id over
    lt_parameter; now reads the real neuract / CONSUMER_SCHEMA columns — neuract is uniform + self-describing.)"""
    cols = sorted(c for c in real_table_cols(table) if c not in _SKIP)
    return [[c] + describe(c) for c in cols]


def window_nonnull(table, n=None):
    """Columns with >=1 NON-NULL value across the last `n` rows (DB knob layer1b.has_data_window_rows, default 20) —
    the HONEST per-column has_data flag for the basket AI. latest_nonnull (single latest row) stays for callers that
    genuinely want the instantaneous state; this windowed form fixes two lies of the latest-row-only flag [hardening]:
      · an intermittent column with real history but null at the last sample flagged N ('Prefer has_data=Y' then
        biased the AI away from a real column);
      · nothing changes for padded-zero columns (0 is non-null) — those are the meaningful-fingerprint's concern.
    Falls back to latest_nonnull semantics when the window read fails (never raises)."""
    from config.app_config import cfg
    n = int(n or cfg("layer1b.has_data_window_rows", 20))
    ob = f'ORDER BY {ts_order_expr(DATA_TS_COL)} DESC' if DATA_TS_COL in real_table_cols(table) else ""
    try:
        rows = q(DATA_DB, f'SELECT to_jsonb(t) FROM (SELECT * FROM {CONSUMER_SCHEMA}."{table}" {ob} LIMIT {n}) t')
    except Exception:
        return latest_nonnull(table)
    out = set()
    for r in rows or []:
        if not r or not r[0]:
            continue
        try:
            d = json.loads(r[0])
        except Exception:
            continue
        out |= {k for k, v in d.items() if v not in (None, "")}
    return out


def latest_nonnull(table):
    # Order by the configured timestamp column CAST (DATA_TS_CAST) to read the GENUINE LATEST row — neuract stores
    # timestamp_utc as ISO-8601 TEXT with MIXED tz offsets (+00:00 → +05:30 writer switch), and a text sort is
    # chronological only within one offset (the latent sibling of the stale-'ts' bug). Guard: only order if the
    # column exists on this table.
    ob = f'ORDER BY {ts_order_expr(DATA_TS_COL)} DESC' if DATA_TS_COL in real_table_cols(table) else ""
    rows = q(DATA_DB, f'SELECT to_jsonb(t) FROM {CONSUMER_SCHEMA}."{table}" t {ob} LIMIT 1')
    if not rows or not rows[0] or not rows[0][0]:
        return set()
    try:
        d = json.loads(rows[0][0])
    except Exception:
        return set()
    return {k for k, v in d.items() if v not in (None, "")}
