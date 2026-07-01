"""Shared data-table shape + timezone config for the lt_panels services layer.

This module carries the small set of constants every other services sub-module
depends on. Keep it dependency-free (only stdlib + config.databases) so the
other sub-modules can import it without risking an import cycle.

Data-table shape (config-driven)
--------------------------------
The raw neuract per-meter tables are ONE meter per table: their timestamp
column is ``timestamp_utc`` and there is NO ``panel_id`` column. The old compat
views had an implicit ``ts`` column + a ``panel_id`` discriminator. We read the
shape from config so flipping ``DATA_HAS_PANEL_ID`` / ``DATA_TS_COL`` restores
the old multi-panel behaviour without touching the query code.

  * ``_TSQ``        — the quoted real timestamp column, e.g. ``"timestamp_utc"``.
  * ``_PANEL_POS``  — WHERE fragment for positional (%s) execute calls.
  * ``_PANEL_NAMED``— WHERE fragment for named (%(panel_id)s) execute calls.
When ``DATA_HAS_PANEL_ID`` is False the fragments collapse to a tautology that
still *consumes* the panel_id param (so placeholder counts stay identical),
but matches every row of the single-meter table.
"""

from zoneinfo import ZoneInfo

try:
    from config.databases import DATA_TS_COL, DATA_TS_CAST, DATA_HAS_PANEL_ID
except Exception:  # pragma: no cover — defensive fallback to neuract defaults
    DATA_TS_COL = 'timestamp_utc'
    DATA_TS_CAST = '::timestamptz'
    DATA_HAS_PANEL_ID = False

# neuract stores timestamp_utc as ISO-8601 TEXT, so every time-math use (>=, BETWEEN, date_trunc, extract, ORDER BY)
# needs a cast. Baking it into _TSQ fixes all of them at one point; harmless no-op if the column is already timestamptz.
_TSQ = '"' + DATA_TS_COL + '"' + DATA_TS_CAST          # e.g. "timestamp_utc"::timestamptz
_PANEL_POS   = 'panel_id = %s'            if DATA_HAS_PANEL_ID else '(%s::text IS NULL OR TRUE)'
_PANEL_NAMED = 'panel_id = %(panel_id)s'  if DATA_HAS_PANEL_ID else '(%(panel_id)s::text IS NULL OR TRUE)'


# Local timezone the frontend operates in. Drives:
#   * `resolve_range('today'/'this_week'/'this_month')` boundaries — so
#     "Today" on an IST screen means IST midnight → now, not UTC midnight.
#   * `_bucket_expr()` — so hourly / daily buckets align to IST :00 marks
#     instead of UTC :30 marks.
# Wire frames + DB storage stay UTC (preserves BE-3's invariants); only
# the human-meaningful presets and bucket edges shift to local.
LOCAL_TZ = ZoneInfo('Asia/Kolkata')
_LOCAL_TZ_NAME = 'Asia/Kolkata'  # used in raw SQL — must match LOCAL_TZ.key
