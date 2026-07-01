"""Load Anomalies page — date-bucketed load profile + surge/dip events.

Polymorphic history dispatcher serving the Load Anomalies chart on the
Energy & Power tab for transformer / UPS / LT panel. Computes the
Expected Range band on-the-fly from the windowed `kpi_kw_load_pct_of_rated`
series (mean ± k·σ), counts surge/dip events as buckets that crossed the
band edges — no separate event-counter columns needed.

Same shape across the 3 implemented types; the only per-type variation
is the K-σ band width (lt panel has more variable load → wider band).
"""
from .._history_base import (
    BaseHistoryStrategy, StubHistoryStrategy, _BaseHistoryDispatcher,
    argmax_bucket,
)


def _mean_and_stddev(values):
    xs = [v for v in values if v is not None]
    if not xs:
        return None, None
    mean = sum(xs) / len(xs)
    if len(xs) == 1:
        return mean, 0.0
    var = sum((x - mean) ** 2 for x in xs) / len(xs)
    return mean, var ** 0.5


class _BaseLoadAnomalies(BaseHistoryStrategy):
    """Shared compute_kpis for transformer / UPS / LT load anomalies.

    Subclass and set `band_k_sigma` to tune how wide the Expected Range
    band sits relative to the historical mean.
    """
    band_k_sigma: float = 1.0

    columns = [
        'kpi_kw_load_pct_of_rated',
        'kpi_load_factor',
        'active_power_total_kw',
    ]

    def compute_kpis(self, buckets):
        if not buckets:
            return {
                'present_load_pct': None,
                'peak_load_pct': None, 'peak_load_pct_at': None,
                'load_factor_pct': None,
                'expected_load_pct': None,
                'expected_band_upper_pct': None,
                'expected_band_lower_pct': None,
                'band_k_sigma': self.band_k_sigma,
                'surge_events_count': 0, 'dip_events_count': 0,
                'surge_events': [], 'dip_events': [],
                'bucket_count': 0,
            }

        # Baseline + band from the bucket-avg load %
        avgs = [b.get('kpi_kw_load_pct_of_rated_avg') for b in buckets]
        baseline_mean, baseline_sigma = _mean_and_stddev(avgs)
        if baseline_mean is not None and baseline_sigma is not None:
            band_upper = baseline_mean + self.band_k_sigma * baseline_sigma
            band_lower = max(0.0, baseline_mean - self.band_k_sigma * baseline_sigma)
        else:
            band_upper = band_lower = None

        # Surge / dip event markers — buckets whose avg crossed the band edges
        surge_events, dip_events = [], []
        if band_upper is not None and band_lower is not None:
            for b in buckets:
                avg_v = b.get('kpi_kw_load_pct_of_rated_avg')
                if avg_v is None:
                    continue
                if avg_v > band_upper:
                    surge_events.append({
                        'at': b.get('bucket'),
                        'load_pct': avg_v,
                        'deviation_pct': avg_v - baseline_mean,
                    })
                elif avg_v < band_lower:
                    dip_events.append({
                        'at': b.get('bucket'),
                        'load_pct': avg_v,
                        'deviation_pct': avg_v - baseline_mean,
                    })

        peak_v, peak_at = argmax_bucket(buckets, 'kpi_kw_load_pct_of_rated_max', prefer='max')
        last = buckets[-1]

        # Sample-weighted load factor over the window
        weighted_sum, weight = 0.0, 0
        for b in buckets:
            lf = b.get('kpi_load_factor_avg')
            n = b.get('samples') or 0
            if lf is not None and n:
                weighted_sum += lf * n
                weight += n
        load_factor = (weighted_sum / weight) if weight else None

        return {
            'present_load_pct':        last.get('kpi_kw_load_pct_of_rated_avg'),
            'peak_load_pct':           peak_v,
            'peak_load_pct_at':        peak_at,
            'load_factor_pct':         (load_factor * 100) if load_factor is not None else None,
            'expected_load_pct':       baseline_mean,
            'expected_band_upper_pct': band_upper,
            'expected_band_lower_pct': band_lower,
            'band_k_sigma':            self.band_k_sigma,
            'surge_events_count':      len(surge_events),
            'dip_events_count':        len(dip_events),
            'surge_events':            surge_events,
            'dip_events':              dip_events,
            'bucket_count':            len(buckets),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Per-type concrete strategies
# ─────────────────────────────────────────────────────────────────────────────

class TransformerLoadAnomalies(_BaseLoadAnomalies):
    """Tighter expected band — transformer load follows shift schedule."""
    band_k_sigma = 1.0


class UpsLoadAnomalies(_BaseLoadAnomalies):
    """UPS load is steady — narrow band catches more anomalies."""
    band_k_sigma = 0.8


class LtPanelLoadAnomalies(_BaseLoadAnomalies):
    """LT panels see mixed feeders — wider band reduces false positives."""
    band_k_sigma = 1.2


# APFC sees mixed load too — use the LT panel band width
class ApfcLoadAnomalies(_BaseLoadAnomalies):
    band_k_sigma = 1.2


# Remaining types still spec-pending
class HtPanelLoadAnomalies(StubHistoryStrategy):    pass
class SubPanelLoadAnomalies(StubHistoryStrategy):   pass


# ─────────────────────────────────────────────────────────────────────────────
# Dispatcher
# ─────────────────────────────────────────────────────────────────────────────

class LoadAnomaliesDispatcher(_BaseHistoryDispatcher):
    PAGE_CODE = 'load-anomalies'
    STRATEGIES = {
        'lt_panel':    LtPanelLoadAnomalies,
        'transformer': TransformerLoadAnomalies,
        'ht_panel':    HtPanelLoadAnomalies,
        'ups':         UpsLoadAnomalies,
        'apfc':        ApfcLoadAnomalies,
        'sub_panel':   SubPanelLoadAnomalies,
    }
