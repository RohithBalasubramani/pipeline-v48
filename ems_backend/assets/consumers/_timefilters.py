"""Shared range × sampling time-filter vocabulary for the asset deep tabs.

Ported from lt_panels so the asset history charts (Thermal & Life, Loss
Analysis, …) speak exactly the same preset vocabulary the frontend dropdowns
use. Each filtered widget uses this independently (per-widget filter state).

  * accepts the frontend vocab (`last-7-days`, `daily`, `custom-range`) + aliases;
  * validates range × sampling combos;
  * resolves a window + builds chronological IST-anchored bucket edges;
  * labels buckets per the design system (HH:MM / A·B·C / D-N·Today / W-N·This W / DD).
"""
from datetime import datetime, timedelta, timezone

from ..services import resolve_range, LOCAL_TZ


SAMPLING_BY_RANGE: dict[str, tuple[str, ...]] = {
    'today':        ('hourly', 'shift'),
    'yesterday':    ('hourly', 'shift'),
    'last-7-days':  ('daily',),
    'last-30-days': ('daily', 'weekly'),
    'this-month':   ('daily', 'weekly'),
    'last-month':   ('daily', 'weekly'),
    'custom-range': ('hourly', 'shift', 'daily', 'weekly'),
}
BUCKET_SECONDS_BY_SAMPLING = {
    'hourly': 3 * 3600, 'shift': 8 * 3600, 'daily': 86_400, 'weekly': 7 * 86_400,
}

_RANGE_ALIASES = {
    'today': 'today', 'yesterday': 'yesterday',
    'last-7-days': 'last-7-days', 'last_7d': 'last-7-days',
    'last_week': 'last-7-days', 'last-week': 'last-7-days',
    'this-month': 'this-month', 'this_month': 'this-month',
    'last-month': 'last-month', 'last_month': 'last-month',
    'last-30-days': 'last-30-days', 'last_30d': 'last-30-days', 'last-30d': 'last-30-days',
    'custom-range': 'custom-range', 'custom': 'custom-range',
}
_SAMPLING_ALIASES = {
    'hourly': 'hourly', 'shift': 'shift',
    'daily': 'daily', 'day': 'daily',
    'weekly': 'weekly', 'week': 'weekly',
}

_SHIFT_NAME = {0: 'A', 8: 'B', 16: 'C'}   # IST start-hour → shift name


def canonical_range(v: str) -> str | None:
    return _RANGE_ALIASES.get((v or '').strip().lower())


def canonical_sampling(v: str) -> str | None:
    return _SAMPLING_ALIASES.get((v or '').strip().lower())


def default_sampling_for(preset: str) -> str:
    return SAMPLING_BY_RANGE.get(preset, ('hourly',))[0]


def validate_range_sampling(preset: str, sampling: str) -> str | None:
    """None if the combo is legal; else a precise error message."""
    if preset not in SAMPLING_BY_RANGE:
        return f"range='{preset}' not supported. Allowed: {', '.join(sorted(SAMPLING_BY_RANGE))}"
    if sampling not in BUCKET_SECONDS_BY_SAMPLING:
        return f"sampling='{sampling}' not supported. Allowed: hourly, shift, daily, weekly"
    allowed = SAMPLING_BY_RANGE[preset]
    if sampling not in allowed:
        return (f"sampling='{sampling}' not allowed for range='{preset}'. "
                f"Allowed: {', '.join(allowed)}")
    return None


def make_bucket_labels(bucket_starts: list[datetime], sampling: str,
                       preset: str, window_end: datetime) -> list[str]:
    local_starts = [ts.astimezone(LOCAL_TZ) for ts in bucket_starts]
    if sampling == 'hourly':
        return [ts.strftime('%H:%M') for ts in local_starts]
    if sampling == 'shift':
        return [_SHIFT_NAME.get(ts.hour, ts.strftime('%H:%M')) for ts in local_starts]
    if sampling == 'daily':
        today_local = datetime.now(LOCAL_TZ).date()
        if preset in ('this-month', 'last-month'):
            return [ts.strftime('%d') for ts in local_starts]
        out = []
        for ts in local_starts:
            delta = (today_local - ts.date()).days
            out.append('Today' if delta <= 0 else f'D-{delta}')
        return out
    if sampling == 'weekly':
        n = len(local_starts)
        if preset == 'this-month':
            return [('This W' if i == n - 1 else f'W-{n - 1 - i}') for i in range(n)]
        return [f'W-{n - i}' for i in range(n)]
    return [ts.strftime('%d %b') for ts in local_starts]


def build_bucket_edges(preset: str, sampling: str,
                       custom_start: str | None = None,
                       custom_end: str | None = None,
                       timeline_time: datetime | None = None
                       ) -> list[tuple[datetime, datetime, str]]:
    """Resolve (preset, sampling) → chronological [(start, end, label)], IST-anchored."""
    if preset == 'custom-range':
        start, end = resolve_range(None, custom_start, custom_end)
    else:
        start, end = resolve_range(preset, None, None)
    if timeline_time is not None and preset in ('today', 'yesterday'):
        end = min(end, timeline_time)

    bucket_seconds = BUCKET_SECONDS_BY_SAMPLING[sampling]
    local_start = start.astimezone(LOCAL_TZ)
    if sampling == 'weekly':
        if preset in ('this-month', 'last-month'):
            local_start = local_start.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            local_start = (local_start - timedelta(days=local_start.weekday())
                           ).replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        hour_block = bucket_seconds // 3600
        anchored_hour = (local_start.hour // hour_block) * hour_block if hour_block else 0
        local_start = local_start.replace(hour=anchored_hour, minute=0, second=0, microsecond=0)

    cursor = local_start.astimezone(timezone.utc)
    step = timedelta(seconds=bucket_seconds)
    starts: list[datetime] = []
    while cursor < end:
        starts.append(cursor)
        cursor += step
    if not starts:
        starts = [start]
    labels = make_bucket_labels(starts, sampling, preset, end)
    return [(s, s + step, lbl) for s, lbl in zip(starts, labels)]
