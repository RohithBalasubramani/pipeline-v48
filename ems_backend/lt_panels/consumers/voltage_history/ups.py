"""Voltage History — UPS strategy.

Serves the Voltage History card on the UPS Voltage & Current tab.

Per-bucket aggregates: AVG/MIN/MAX of voltage_r/y/b_n, voltage_avg,
voltage_unbalance_pct, kpi_voltage_deviation_pct. Plus the latest values
of sag_events_24h, swell_events_24h, primary_voltage_event_today.

KPIs returned alongside the bucket array:
  max_deviation_pct         worst |deviation %| over the window
  max_deviation_at          timestamp of that bucket
  max_unbalance_pct         peak voltage_unbalance_pct over the window
  max_unbalance_at          timestamp of that bucket
  worst_spread_v            max (any-phase-high − any-phase-low) across buckets
  worst_spread_at           timestamp of that bucket
  worst_spread_pair         phase-pair label, e.g. "B-Y"
  expected_band_upper_v     mean(voltage_avg_avg) + k·σ — drives green Expected Range upper
  expected_band_lower_v     mean(voltage_avg_avg) − k·σ — drives green Expected Range lower
  sag_events                latest bucket's sag_events_24h
  swell_events              latest bucket's swell_events_24h
  primary_event             latest bucket's primary_voltage_event_today
"""
from .._history_base import BaseHistoryStrategy, argmax_bucket
from ._events_mixin import PhaseEventsMixin

# Expected-Range band width. 1.0 ≈ one-sigma band (~68% of buckets inside).
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


class UpsVoltageHistory(PhaseEventsMixin, BaseHistoryStrategy):
    columns = [
        'voltage_r_n', 'voltage_y_n', 'voltage_b_n',
        'voltage_avg',
        'voltage_unbalance_pct',
        'kpi_voltage_deviation_pct',
    ]
    extra_aggregates = {
        'sag_events':   'MAX(sag_events_24h)',
        'swell_events': 'MAX(swell_events_24h)',
        # Text columns — take the latest non-null over the bucket
        'primary_event_text': 'MAX(primary_voltage_event_today)',
        'worst_pair_text':    'MAX(worst_spread_today_pair)',
    }

    def compute_kpis(self, buckets):
        # ── Extreme deviation across the window (signed; pick larger |·|) ──
        max_dev, max_dev_at = argmax_bucket(buckets, 'kpi_voltage_deviation_pct_max', prefer='max')
        min_dev, min_dev_at = argmax_bucket(buckets, 'kpi_voltage_deviation_pct_min', prefer='min')
        if max_dev is None and min_dev is None:
            extreme_dev, extreme_dev_at = None, None
        elif max_dev is None:
            extreme_dev, extreme_dev_at = min_dev, min_dev_at
        elif min_dev is None:
            extreme_dev, extreme_dev_at = max_dev, max_dev_at
        else:
            extreme_dev, extreme_dev_at = (
                (max_dev, max_dev_at) if abs(max_dev) >= abs(min_dev)
                else (min_dev, min_dev_at)
            )

        max_unb, max_unb_at = argmax_bucket(buckets, 'voltage_unbalance_pct_max', prefer='max')

        # ── Worst phase-spread across the window ────────────────────────
        worst_spread, worst_spread_at, worst_spread_pair = None, None, None
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

        # ── Expected Range band: mean ± k·σ of bucket voltage_avg_avg ───
        avg_series = [b.get('voltage_avg_avg') for b in buckets]
        baseline_mean, baseline_sigma = _mean_and_stddev(avg_series)
        if baseline_mean is not None and baseline_sigma is not None:
            band_upper = baseline_mean + BAND_K_SIGMA * baseline_sigma
            band_lower = max(0.0, baseline_mean - BAND_K_SIGMA * baseline_sigma)
        else:
            band_upper = band_lower = None

        # ── Latest text labels (primary event, worst-spread pair) ──────
        latest = buckets[-1] if buckets else {}
        return {
            'max_deviation_pct':     extreme_dev,
            'max_deviation_at':      extreme_dev_at,
            'max_unbalance_pct':     max_unb,
            'max_unbalance_at':      max_unb_at,
            'worst_spread_v':        worst_spread,
            'worst_spread_at':       worst_spread_at,
            'worst_spread_pair':     worst_spread_pair or latest.get('worst_pair_text'),
            'expected_band_upper_v': band_upper,
            'expected_band_lower_v': band_lower,
            'band_k_sigma':          BAND_K_SIGMA,
            'sag_events':            latest.get('sag_events'),
            'swell_events':          latest.get('swell_events'),
            'primary_event':         latest.get('primary_event_text'),
            'bucket_count':          len(buckets),
        }
