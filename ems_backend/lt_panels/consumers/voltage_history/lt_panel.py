"""Voltage History — LT panel strategy. Ported from legacy VoltageHistoryConsumer."""
from .._history_base import BaseHistoryStrategy, argmax_bucket
from ._events_mixin import PhaseEventsMixin


class LtPanelVoltageHistory(PhaseEventsMixin, BaseHistoryStrategy):
    columns = [
        'voltage_r_n', 'voltage_y_n', 'voltage_b_n',
        'voltage_unbalance_pct',
        'kpi_voltage_deviation_pct',
    ]
    # Event counts/records are derived from the boolean event-flag columns
    # in PhaseEventsMixin.extra_snapshot (top-level `event_counts` /
    # `events` on the frame). Per-bucket sag/swell aggregates are NOT
    # included here — the previous MAX(sag_events_24h) was reading the
    # simulator's rolling counter, which produced the same value in every
    # bucket and didn't reflect real per-bucket event count.

    def compute_kpis(self, buckets):
        max_dev_v, max_dev_ts = argmax_bucket(buckets, 'kpi_voltage_deviation_pct_max', prefer='max')
        min_dev_v, min_dev_ts = argmax_bucket(buckets, 'kpi_voltage_deviation_pct_min', prefer='min')
        if max_dev_v is None and min_dev_v is None:
            extreme_dev, extreme_dev_ts = None, None
        elif max_dev_v is None:
            extreme_dev, extreme_dev_ts = min_dev_v, min_dev_ts
        elif min_dev_v is None:
            extreme_dev, extreme_dev_ts = max_dev_v, max_dev_ts
        else:
            extreme_dev, extreme_dev_ts = (
                (max_dev_v, max_dev_ts) if abs(max_dev_v) >= abs(min_dev_v)
                else (min_dev_v, min_dev_ts)
            )

        max_unb_v, max_unb_ts = argmax_bucket(buckets, 'voltage_unbalance_pct_max', prefer='max')

        worst_spread = None
        worst_spread_at = None
        worst_spread_pair = None
        for b in buckets:
            phases = {p: (b.get(f'voltage_{p}_n_max'), b.get(f'voltage_{p}_n_min'))
                      for p in ('r', 'y', 'b')}
            highs = {p: hi for p, (hi, _) in phases.items() if hi is not None}
            lows  = {p: lo for p, (_, lo) in phases.items() if lo is not None}
            if highs and lows:
                hi_phase = max(highs, key=highs.get)
                lo_phase = min(lows,  key=lows.get)
                spread = highs[hi_phase] - lows[lo_phase]
                if worst_spread is None or spread > worst_spread:
                    worst_spread     = spread
                    worst_spread_at  = b.get('bucket')
                    worst_spread_pair = f'{hi_phase.upper()}-{lo_phase.upper()}'

        return {
            'max_deviation_pct':  extreme_dev,
            'max_deviation_at':   extreme_dev_ts,
            'max_unbalance_pct':  max_unb_v,
            'max_unbalance_at':   max_unb_ts,
            'worst_spread_v':     worst_spread,
            'worst_spread_at':    worst_spread_at,
            'worst_spread_pair':  worst_spread_pair,
            # sag/swell totals now live on the frame top-level as
            # `event_counts` (from PhaseEventsMixin), since they're derived
            # from boolean rising-edge counts, not from voltage buckets.
        }
