"""Shared mixin for voltage-history strategies: discrete event records.

Reads the simulator's per-event boolean columns (`sag_event_active`,
`swell_event_active`, `current_imbalance_event_active`,
`neutral_stress_event_active`) — same single source of truth as the live
voltage-current page (`PccPanelVoltageCurrent`). Each FALSE→TRUE rising
edge counts as one event; per-bucket counts and the discrete events list
both come from that crossing, so totals always reconcile.

Surfaced on the snapshot frame as:
  events[]            discrete {ts, type} records (capped at max_events)
  event_counts        uncapped per-type totals over the resolved window
  event_thresholds    simulator's percentage thresholds (informational)
"""
import logging

from ...services import (
    fetch_bool_event_records, fetch_bool_event_counts_per_bucket,
    get_table_columns,
)


logger = logging.getLogger(__name__)


# (boolean column on the panel table → wire-format event type label)
_EVENT_COLUMNS = (
    ('sag_event_active',                'sag'),
    ('swell_event_active',              'swell'),
    ('current_imbalance_event_active',  'current'),
    ('neutral_stress_event_active',     'neutral'),
)


# Same values the simulator uses internally to flip the booleans —
# returned as informational metadata for the frontend (no math is done
# on these here, counts come from the booleans directly).
_THRESHOLDS = {
    'sag_pct_of_nominal':   92,
    'swell_pct_of_nominal': 108,
    'i_unbalance_pct':      8,
    'neutral_pct_of_phase': 15,
}


class PhaseEventsMixin:
    """Adds an `extra_snapshot` that ships discrete event records + totals.

    Subclass with `BaseHistoryStrategy`. `max_events` caps the records list
    per event-type to keep wire-frames small; the count totals are uncapped.
    """
    max_events: int = 200

    def extra_snapshot(self, start, end) -> dict:
        link, table, panel_id = self.mfm.db_link, self.mfm.table_name, self.mfm.panel_id

        # Skip cleanly on tables that don't have the boolean event columns
        # yet (e.g. transformer / UPS / HT). Those pages keep their existing
        # per-bucket sag/swell KPIs (rolling-counter based) instead.
        cols = get_table_columns(link, table)
        if not any(col in cols for col, _ in _EVENT_COLUMNS):
            return {}

        records: list = []
        counts: dict = {}
        for col, etype in _EVENT_COLUMNS:
            try:
                per_bucket = fetch_bool_event_counts_per_bucket(
                    link, table, panel_id, col, start, end,
                    bucket_seconds=int((end - start).total_seconds()) or 1,
                )
                counts[etype] = sum(per_bucket.values())
                for rec in fetch_bool_event_records(
                    link, table, panel_id, col, start, end,
                    max_events=self.max_events,
                ):
                    records.append({'ts': rec['ts'], 'type': etype})
            except Exception as exc:
                logger.warning(
                    'voltage-history events: %s on mfm=%s col=%s: %s',
                    type(exc).__name__, getattr(self.mfm, 'id', None), col, exc,
                )
                counts.setdefault(etype, 0)

        records.sort(key=lambda e: e['ts'])
        return {
            'events':           records,
            'event_counts':     counts,
            'event_thresholds': _THRESHOLDS,
        }
