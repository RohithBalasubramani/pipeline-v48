"""Single-row + trailing-window row fetchers.

These return raw rows (latest / last-N-seconds / last-N-minutes / static
config) with column-tolerance: columns that don't exist on the table are
dropped from the SQL and padded back as None in the result dicts, so callers
keep their full column shape.
"""

from datetime import timedelta
from typing import Any

from .config import _TSQ, _PANEL_POS
from .connection import _connect, _row_to_dict
from .columns import _select_existing, _pad_missing
from .timeutils import _now


def fetch_live(
    db_link: str,
    table: str,
    panel_id: str,
    columns: list[str] | None = None,
) -> dict[str, Any] | None:
    """Return the latest row for the given panel_id, or None.

    Columns that don't exist on the table are silently dropped from the SQL
    and added back as None in the returned dict, so callers (widget
    strategies in particular) keep their full column shape.
    """
    if not columns:
        select_cols = f'*, {_TSQ} AS ts'
        missing: list[str] = []
    else:
        existing, missing = _select_existing(db_link, table, columns)
        select_cols = ', '.join([f'{_TSQ} AS ts'] + ['"' + c + '"' for c in existing])
    sql = f'SELECT {select_cols} FROM "{table}" WHERE {_PANEL_POS} ORDER BY {_TSQ} DESC LIMIT 1'
    with _connect(db_link) as conn, conn.cursor() as cur:
        cur.execute(sql, (panel_id,))
        row = cur.fetchone()
        return _pad_missing(_row_to_dict(cur, row) if row else None, missing)


def fetch_config_row(
    db_link: str,
    table: str,
    panel_id: str,
) -> dict[str, Any] | None:
    """Return the per-MFM static config row (thresholds, nameplate, ratings).

    Used by `/api/mfm/{id}/config/` to serve chart reference lines, rated
    capacities, and PF/THD/temp limits to the frontend. Config tables exist
    once per MFM type (`transformer_config`, `ups_config`, `lt_panel_config`,
    `ht_panel_config`, `apfc_config`) and are seeded by the simulator on
    init-db; they're not part of the timeseries `panel_readings` flow.

    Returns None if the table doesn't exist or no row matches the panel_id.
    """
    with _connect(db_link) as conn, conn.cursor() as cur:
        try:
            cur.execute(
                f'SELECT * FROM "{table}" WHERE {_PANEL_POS} LIMIT 1',
                (panel_id,),
            )
        except Exception:
            return None
        row = cur.fetchone()
        return _row_to_dict(cur, row) if row else None


def fetch_window(
    db_link: str,
    table: str,
    panel_id: str,
    seconds: int = 30,
    columns: list[str] | None = None,
    limit: int = 5000,
) -> list[dict[str, Any]]:
    """Return rows from the last ``seconds`` seconds, oldest-first.

    Missing columns are padded with None per row (see ``fetch_live``).
    """
    cutoff = _now() - timedelta(seconds=seconds)
    if not columns:
        select_cols = f'*, {_TSQ} AS ts'
        missing: list[str] = []
    else:
        existing, missing = _select_existing(db_link, table, columns)
        select_cols = ', '.join([f'{_TSQ} AS ts'] + ['"' + c + '"' for c in existing])
    sql = (
        f'SELECT {select_cols} FROM "{table}" '
        f'WHERE {_PANEL_POS} AND {_TSQ} >= %s '
        f'ORDER BY {_TSQ} ASC LIMIT %s'
    )
    with _connect(db_link) as conn, conn.cursor() as cur:
        cur.execute(sql, (panel_id, cutoff, limit))
        rows = cur.fetchall()
        return [_pad_missing(_row_to_dict(cur, r), missing) for r in rows]


def fetch_history(
    db_link: str,
    table: str,
    panel_id: str,
    minutes: int = 60,
    columns: list[str] | None = None,
    limit: int = 5000,
) -> list[dict[str, Any]]:
    """Return rows for the last ``minutes`` minutes, oldest-first.

    Missing columns are padded with None per row (see ``fetch_live``).
    """
    cutoff = _now() - timedelta(minutes=minutes)
    if not columns:
        select_cols = f'*, {_TSQ} AS ts'
        missing: list[str] = []
    else:
        existing, missing = _select_existing(db_link, table, columns)
        select_cols = ', '.join([f'{_TSQ} AS ts'] + ['"' + c + '"' for c in existing])
    sql = (
        f'SELECT {select_cols} FROM "{table}" '
        f'WHERE {_PANEL_POS} AND {_TSQ} >= %s '
        f'ORDER BY {_TSQ} ASC LIMIT %s'
    )
    with _connect(db_link) as conn, conn.cursor() as cur:
        cur.execute(sql, (panel_id, cutoff, limit))
        rows = cur.fetchall()
        return [_pad_missing(_row_to_dict(cur, r), missing) for r in rows]
