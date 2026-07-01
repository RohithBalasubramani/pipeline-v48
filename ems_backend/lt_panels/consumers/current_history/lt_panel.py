"""Current History — LT panel strategy. Ported from legacy CurrentHistoryConsumer."""
from .._history_base import BaseHistoryStrategy, argmax_bucket


class LtPanelCurrentHistory(BaseHistoryStrategy):
    columns = [
        'current_r', 'current_y', 'current_b', 'current_neutral',
        'current_avg', 'current_unbalance_pct',
    ]

    def compute_kpis(self, buckets):
        peak = None
        for b in buckets:
            highs = [b.get(f'current_{p}_max') for p in ('r', 'y', 'b')]
            highs = [v for v in highs if v is not None]
            if highs:
                peak = max(highs) if peak is None else max(peak, max(highs))

        weighted_sum, weight = 0.0, 0
        for b in buckets:
            avg = b.get('current_avg_avg')
            n = b.get('samples') or 0
            if avg is not None and n:
                weighted_sum += avg * n
                weight += n
        avg_current = (weighted_sum / weight) if weight else None

        max_unb, max_unb_ts = argmax_bucket(buckets, 'current_unbalance_pct_max', prefer='max')
        neutral_peak, _    = argmax_bucket(buckets, 'current_neutral_max',          prefer='max')

        return {
            'peak_current_a':    peak,
            'average_current_a': avg_current,
            'max_unbalance_pct': max_unb,
            'max_unbalance_at':  max_unb_ts,
            'neutral_peak_a':    neutral_peak,
        }
