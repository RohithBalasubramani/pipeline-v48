"""Current History — Transformer strategy.

Drives the Current History card on the Transformer V&C page:
  - Per-phase R/Y/B line series + Expected Range band (mean ± 1·σ)
  - KPIs: Peak Current, Average Current, Max Unbalance, Neutral Peak
  - Range filter: Today / This Week / This Month (handled by dispatcher)
"""
from .._history_base import BaseHistoryStrategy, argmax_bucket

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


class TransformerCurrentHistory(BaseHistoryStrategy):
    columns = [
        'current_r', 'current_y', 'current_b', 'current_neutral',
        'current_avg',
        'current_unbalance_pct',
    ]

    def compute_kpis(self, buckets):
        if not buckets:
            return {
                'peak_current_a': None, 'average_current_a': None,
                'max_unbalance_pct': None, 'max_unbalance_at': None,
                'neutral_peak_a': None,
                'expected_band_upper_a': None, 'expected_band_lower_a': None,
                'band_k_sigma': BAND_K_SIGMA,
                'bucket_count': 0,
            }

        # Peak phase current across the window
        peak = None
        for b in buckets:
            highs = [b.get(f'current_{p}_max') for p in ('r', 'y', 'b')]
            highs = [v for v in highs if v is not None]
            if highs:
                row_peak = max(highs)
                peak = row_peak if peak is None else max(peak, row_peak)

        # Sample-weighted average current
        weighted_sum, weight = 0.0, 0
        for b in buckets:
            avg = b.get('current_avg_avg')
            n = b.get('samples') or 0
            if avg is not None and n:
                weighted_sum += avg * n
                weight += n
        avg_current = (weighted_sum / weight) if weight else None

        max_unb, max_unb_ts = argmax_bucket(buckets, 'current_unbalance_pct_max', prefer='max')
        neutral_peak, _    = argmax_bucket(buckets, 'current_neutral_max',         prefer='max')

        # Expected Range band — mean ± k·σ of bucket current_avg_avg
        avg_series = [b.get('current_avg_avg') for b in buckets]
        baseline_mean, baseline_sigma = _mean_and_stddev(avg_series)
        if baseline_mean is not None and baseline_sigma is not None:
            band_upper = baseline_mean + BAND_K_SIGMA * baseline_sigma
            band_lower = max(0.0, baseline_mean - BAND_K_SIGMA * baseline_sigma)
        else:
            band_upper = band_lower = None

        return {
            'peak_current_a':        peak,
            'average_current_a':     avg_current,
            'max_unbalance_pct':     max_unb,
            'max_unbalance_at':      max_unb_ts,
            'neutral_peak_a':        neutral_peak,
            'expected_band_upper_a': band_upper,
            'expected_band_lower_a': band_lower,
            'band_k_sigma':          BAND_K_SIGMA,
            'bucket_count':          len(buckets),
        }
