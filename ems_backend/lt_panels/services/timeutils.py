"""Time-window resolution + SQL bucket-expression helpers.

Human-meaningful presets (today / yesterday / this_week / this_month) use
LOCAL_TZ for their boundaries; rolling-window presets (last_24h / last_7d /
last_30d) stay in UTC. Bucket edges align to LOCAL_TZ (IST) while the wire
format stays UTC-aware.
"""

import os
from datetime import datetime, timedelta, timezone

from .config import _TSQ, LOCAL_TZ, _LOCAL_TZ_NAME


def _now():
    """Windowing 'now'. EMS_REFERENCE_NOW (ISO) anchors the live window at the data's latest (neuract ends
    2026-03-26) so trailing windows are non-empty; unset → real now. Lets consumers stay untouched."""
    raw = os.environ.get("EMS_REFERENCE_NOW")
    if raw:
        try:
            dt = datetime.fromisoformat(raw)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            pass
    return datetime.now(timezone.utc)


VALID_SAMPLINGS = {
    'minute', '5min', '15min', '30min', 'hour', 'day',
    # Sub-filter sampling tied to range:
    #   hourly → 3-hour buckets (8 per day) — for today / yesterday
    #   2hour  → 2-hour buckets (12 per day) — for today / yesterday (detail-tab Power Energy Analysis)
    #   shift  → 8-hour buckets aligned to IST 00/08/16 — for today / yesterday
    #   week   → 7-day buckets anchored to IST Monday — for this_month / last_month
    'hourly', '2hour', 'shift', 'week',
}


def _bucket_expr(sampling: str) -> str:
    """SQL expression for bucketing ``ts`` by ``sampling`` — bucket edges
    align to LOCAL_TZ (IST), wire format stays UTC-aware.

    The pattern ``date_trunc('hour', ts AT TIME ZONE 'Asia/Kolkata') AT
    TIME ZONE 'Asia/Kolkata'`` does:
      1. shift the UTC ts to IST wall-clock as a naïve timestamp
      2. truncate that naïve timestamp to the hour
      3. shift back to a UTC TIMESTAMPTZ for serialisation
    Net effect: a 09:00 IST bucket spans 03:30 → 04:30 UTC and ships as a
    proper TIMESTAMPTZ on the wire. Frontend `toLocaleString('en-IN', …)`
    converts it back to "09:00" cleanly.
    """
    tz = f"'{_LOCAL_TZ_NAME}'"
    if sampling == 'minute':
        return f"date_trunc('minute', {_TSQ} AT TIME ZONE {tz}) AT TIME ZONE {tz}"
    if sampling == 'hour':
        return f"date_trunc('hour', {_TSQ} AT TIME ZONE {tz}) AT TIME ZONE {tz}"
    if sampling == 'day':
        return f"date_trunc('day', {_TSQ} AT TIME ZONE {tz}) AT TIME ZONE {tz}"
    # Epoch-based bucketing for arbitrary sub-day windows. The pattern below
    # IS subtle — it has to undo a double TZ shift that bit us once already:
    #   1. `ts AT TIME ZONE 'Asia/Kolkata'`  → TIMESTAMPTZ → naive IST wall-clock
    #   2. `extract(epoch from <naive>)`     → in UTC session this treats the
    #                                          naive as UTC, so the "epoch" is
    #                                          actually shifted +5:30h from real.
    #   3. `floor(... / seconds) * seconds`  → quantize to bucket size.
    #   4. `to_timestamp(<epoch>)`           → TIMESTAMPTZ (UTC) for that epoch.
    #   5. `... AT TIME ZONE 'UTC'`          → drop TZ, keep wall-clock numbers.
    #   6. `... AT TIME ZONE 'Asia/Kolkata'` → reinterpret as IST → TIMESTAMPTZ.
    # Without step 5, step 6 would convert UTC→IST a second time, double-shifting.
    if sampling in ('5min', '15min', '30min', 'hourly', '2hour', 'shift'):
        seconds = {
            '5min':  300, '15min':  900, '30min': 1800,
            'hourly': 3 * 3600,
            '2hour':  2 * 3600,
            'shift':  8 * 3600,
        }[sampling]
        return (
            f"((to_timestamp(floor(extract(epoch from {_TSQ} AT TIME ZONE {tz}) "
            f"/ {seconds}) * {seconds}) AT TIME ZONE 'UTC') AT TIME ZONE {tz})"
        )
    # Weekly buckets — date_trunc('week', ...) anchors to ISO Monday,
    # which matches the existing `this_week` preset's Mon-anchored window.
    if sampling == 'week':
        return f"date_trunc('week', {_TSQ} AT TIME ZONE {tz}) AT TIME ZONE {tz}"
    raise ValueError(f'Invalid sampling: {sampling}')


def _local_midnight(dt_local: datetime) -> datetime:
    """Zero out hours/minutes/seconds/microseconds while staying in the same tz."""
    return dt_local.replace(hour=0, minute=0, second=0, microsecond=0)


def _parse_boundary(value: str, is_end: bool) -> datetime:
    """Parse an ISO 8601 datetime *or* a bare ``YYYY-MM-DD`` date.

    Bare dates are anchored to **IST midnight** of the named day. For ``end``
    we go to the START of the named day (i.e. exclusive upper bound matching
    the preset semantics: ``end = next day's midnight`` for full inclusion
    means the caller should pass the day *after* the last one they want).
    Pass a bare ISO 8601 datetime if you need a non-midnight cutoff.
    """
    v = value.strip()
    if 'T' in v or ' ' in v:
        return datetime.fromisoformat(v)
    # Bare YYYY-MM-DD → IST midnight of that day.
    d = datetime.fromisoformat(v + 'T00:00:00')
    return d.replace(tzinfo=LOCAL_TZ).astimezone(timezone.utc)


def resolve_range(
    preset: str | None,
    start: str | None,
    end: str | None,
) -> tuple[datetime, datetime]:
    """Resolve a date-range from explicit start/end or a named preset.

    Human-meaningful presets (today / yesterday / this_week / this_month)
    use LOCAL_TZ for their boundaries — "today" on a screen in IST means
    IST midnight → now, not UTC midnight. Rolling-window presets
    (last_24h / last_7d / last_30d) are TZ-independent and stay in UTC.

    All returned datetimes are UTC tz-aware so the SQL WHERE clause works
    against the TIMESTAMPTZ `ts` column.

    Explicit ``start`` / ``end`` accept both full ISO 8601 datetimes
    (``2026-05-27T08:00:00Z``) and bare dates (``2026-05-27``). Bare dates
    are interpreted as IST midnight of that day so that the result lines
    up with the rest of the preset semantics.
    """
    if start and end:
        return _parse_boundary(start, is_end=False), _parse_boundary(end, is_end=True)

    now_utc   = _now()
    now_local = now_utc.astimezone(LOCAL_TZ)
    p = (preset or 'today').lower()

    if p == 'today':
        start_local = _local_midnight(now_local)
        return start_local.astimezone(timezone.utc), now_utc
    if p == 'yesterday':
        end_local   = _local_midnight(now_local)
        start_local = end_local - timedelta(days=1)
        return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)
    if p in ('this_week', 'this-week', 'thisweek'):
        start_local = _local_midnight(now_local) - timedelta(days=now_local.weekday())
        return start_local.astimezone(timezone.utc), now_utc
    if p in ('this_month', 'this-month', 'thismonth'):
        start_local = _local_midnight(now_local).replace(day=1)
        return start_local.astimezone(timezone.utc), now_utc
    if p in ('last_month', 'last-month', 'lastmonth'):
        # Previous IST calendar month: [first-of-prev-month, first-of-this-month).
        this_month_start_local = _local_midnight(now_local).replace(day=1)
        prev_month_end_local   = this_month_start_local
        # Step back one day to land inside the previous month, then snap to its 1st.
        prev_month_start_local = (prev_month_end_local - timedelta(days=1)).replace(day=1)
        return (prev_month_start_local.astimezone(timezone.utc),
                prev_month_end_local.astimezone(timezone.utc))

    # Rolling-window presets — local-tz-irrelevant
    if p in ('last_24h', 'last-24h'):
        return now_utc - timedelta(hours=24), now_utc
    if p in ('last_7d', 'last-7d', 'last_week', 'last-week'):
        # Trailing 7×24 h — tz-irrelevant. Kept for back-compat with the
        # history sockets / older API consumers.
        return now_utc - timedelta(days=7), now_utc
    if p == 'last-7-days':
        # 7 *calendar* days inclusive of today: D-6 ... Today (IST-anchored).
        # The frontend's "last 7 days" preset expects exactly 7 daily buckets.
        start_local = _local_midnight(now_local) - timedelta(days=6)
        return start_local.astimezone(timezone.utc), now_utc
    if p in ('last_30d', 'last-30d'):
        return now_utc - timedelta(days=30), now_utc
    if p == 'last-30-days':
        # 30 calendar days inclusive of today: D-29 ... Today (IST-anchored).
        start_local = _local_midnight(now_local) - timedelta(days=29)
        return start_local.astimezone(timezone.utc), now_utc

    # Unknown preset → default to "today"
    start_local = _local_midnight(now_local)
    return start_local.astimezone(timezone.utc), now_utc
