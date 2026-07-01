"""Voltage History — Transformer strategy.

Drives the Voltage History card on the Transformer V&C page:
  - Per-phase R/Y/B line series + Expected Range band (mean ± 1·σ)
  - KPIs: Max Deviation, Worst Spread (with phase pair), Primary Event,
    Swell/Sag counters
  - Range filter: Today / This Week / This Month (handled by dispatcher)
"""
from .._history_base import BaseHistoryStrategy, argmax_bucket
from ._events_mixin import PhaseEventsMixin

BAND_K_SIGMA = 1.0


def _mean_and_stddev(values):
    xs = [v for v in values if v is not None]
    if not xs:
        return None, None
    mean = sum(xs) / len(xs)
    if len(xs) == 1:
        return mean, 0.0
    var = sum((x - mean) ** 2 for x in xs) / len(xs)
    return mean, var ** 0.5


class TransformerVoltageHistory(PhaseEventsMixin, BaseHistoryStrategy):
    columns = [
        # L-N phase voltages (per-phase line series)
        'voltage_r_n',
        'voltage_y_n',
        'voltage_b_n',
        'voltage_avg',                  # baseline for Expected Range band
        # Deviation & unbalance for KPI strip
        'kpi_voltage_deviation_pct',
        'voltage_unbalance_pct',
    ]
    extra_aggregates = {
        'sag_events':         'MAX(sag_events_24h)',
        'swell_events':       'MAX(swell_events_24h)',
        # "Primary Event" — most recent event tag in the bucket window
        'primary_event_text': 'MAX(primary_voltage_event_today)',
        # Pre-computed worst-pair label, if simulator wrote one for the bucket
        'worst_pair_text':    'MAX(worst_spread_today_pair)',
    }

    def compute_kpis(self, buckets):
        if not buckets:
            return {
                'max_deviation_pct': None, 'max_deviation_at': None,
                'worst_spread_v': None, 'worst_spread_at': None,
                'worst_spread_pair': None,
                'expected_band_upper_v': None, 'expected_band_lower_v': None,
                'band_k_sigma': BAND_K_SIGMA,
                'primary_event': None, 'primary_event_at': None,
                'sag_events': None, 'swell_events': None,
                'bucket_count': 0,
            }

        # Max deviation (signed): take whichever extreme has greater magnitude
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

        # Worst spread across phases per bucket
        worst_spread, worst_spread_at, worst_pair = None, None, None
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
                    worst_spread, worst_spread_at = spread, b.get('bucket')
                    worst_pair = f'{hi_phase.upper()}-{lo_phase.upper()}'

        # Expected Range band — mean ± k·σ of bucket voltage_avg_avg
        avg_series = [b.get('voltage_avg_avg') for b in buckets]
        baseline_mean, baseline_sigma = _mean_and_stddev(avg_series)
        if baseline_mean is not None and baseline_sigma is not None:
            band_upper = baseline_mean + BAND_K_SIGMA * baseline_sigma
            band_lower = max(0.0, baseline_mean - BAND_K_SIGMA * baseline_sigma)
        else:
            band_upper = band_lower = None

        # Latest text labels
        latest = buckets[-1]
        primary_event = latest.get('primary_event_text')
        primary_event_at = latest.get('bucket') if primary_event else None
        return {
            'max_deviation_pct':     extreme_dev,
            'max_deviation_at':      extreme_dev_ts,
            'worst_spread_v':        worst_spread,
            'worst_spread_at':       worst_spread_at,
            'worst_spread_pair':     worst_pair or latest.get('worst_pair_text'),
            'expected_band_upper_v': band_upper,
            'expected_band_lower_v': band_lower,
            'band_k_sigma':          BAND_K_SIGMA,
            'primary_event':         primary_event,
            'primary_event_at':      primary_event_at,
            'sag_events':            latest.get('sag_events'),
            'swell_events':          latest.get('swell_events'),
            'bucket_count':          len(buckets),
        }
