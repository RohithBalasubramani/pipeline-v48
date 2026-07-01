"""Energy & Power History — UPS strategy.

Serves the two charts on the UPS Energy & Power tab that depend on a range
filter (today / this_week / this_month):

  1. Power Energy Analysis (bar chart)
     - per-bucket: AVG/MIN/MAX of active_power_total_kw, reactive_power_total_kvar
     - hourly average line is the bucket-AVG series itself
     - bar height: stacked active+reactive AVG per bucket

  2. Load Anomalies (line + band)
     - per-bucket: AVG/MIN/MAX of kpi_kw_load_pct_of_rated
     - Expected baseline = mean of all bucket-avgs in the window
     - Expected band = baseline ± k × σ_of_bucket_avgs (k=1 by default)
     - Surge events = buckets whose AVG > upper band
     - Dip   events = buckets whose AVG < lower band

KPIs returned alongside the bucket array (in `kpis`):
  max_load_pct           MAX of bucket-max kpi_kw_load_pct_of_rated
  max_load_pct_at        timestamp of that bucket
  load_factor            window AVG / window MAX active power
  total_active_kwh       Σ (bucket_avg_kw × bucket_hours)
  total_reactive_kvarh   Σ (bucket_avg_kvar × bucket_hours)
  hourly_avg_power_kw    window AVG of active_power_total_kw_avg
  expected_load_pct      baseline (mean of bucket-avg load)
  expected_band_upper    baseline + k·σ
  expected_band_lower    baseline − k·σ
  surge_events_count     buckets above upper band
  dip_events_count       buckets below lower band

Cumulative-counter aware: if you'd rather sum energy from the monotonic
counter, the dispatcher's services.fetch_energy_delta() helper covers it —
this strategy uses the average-power approach to stay consistent with the
hourly bar chart.
"""
from .._history_base import BaseHistoryStrategy, argmax_bucket

# k × σ band width. 1.0 ≈ a normal-distribution one-sigma band (~68% of buckets
# fall inside). Tune from config later (rated_efficiency_pct / surge_threshold_k).
BAND_K_SIGMA = 1.0


def _mean_and_stddev(values: list[float]) -> tuple[float | None, float | None]:
    """Population mean and std-dev. None when there's nothing to average."""
    xs = [v for v in values if v is not None]
    if not xs:
        return None, None
    mean = sum(xs) / len(xs)
    if len(xs) == 1:
        return mean, 0.0
    var = sum((x - mean) ** 2 for x in xs) / len(xs)
    return mean, var ** 0.5


def _seconds_per_bucket(buckets: list[dict]) -> float | None:
    """Infer bucket width in seconds from consecutive bucket timestamps."""
    ts_list = [b.get('bucket') for b in buckets if b.get('bucket') is not None]
    if len(ts_list) < 2:
        return None
    a, b = ts_list[0], ts_list[1]
    try:
        return abs((b - a).total_seconds())
    except AttributeError:
        return None


class UpsEnergyPowerHistory(BaseHistoryStrategy):
    columns = [
        'active_power_total_kw',
        'reactive_power_total_kvar',
        'kpi_kw_load_pct_of_rated',
    ]

    def compute_kpis(self, buckets: list[dict]) -> dict:
        if not buckets:
            return {
                'max_load_pct': None,    'max_load_pct_at': None,
                'load_factor': None,
                'total_active_kwh': None,'total_reactive_kvarh': None,
                'hourly_avg_power_kw': None,
                'expected_load_pct': None,
                'expected_band_upper': None,
                'expected_band_lower': None,
                'surge_events_count': 0, 'dip_events_count': 0,
                'bucket_count': 0,
            }

        # Window-level peak load %
        max_load_pct, max_load_pct_at = argmax_bucket(
            buckets, 'kpi_kw_load_pct_of_rated_max', prefer='max',
        )

        # Load factor over the window = window AVG / window MAX active power
        active_avgs = [b.get('active_power_total_kw_avg') for b in buckets]
        active_maxes = [b.get('active_power_total_kw_max') for b in buckets]
        reactive_avgs = [b.get('reactive_power_total_kvar_avg') for b in buckets]
        load_pct_avgs = [b.get('kpi_kw_load_pct_of_rated_avg') for b in buckets]

        mean_active, _ = _mean_and_stddev(active_avgs)
        clean_maxes = [v for v in active_maxes if v is not None]
        window_max_active = max(clean_maxes) if clean_maxes else None
        load_factor = (
            (mean_active / window_max_active)
            if (mean_active is not None and window_max_active not in (None, 0))
            else None
        )

        # Total energy = Σ (avg_kw × bucket_hours)
        sec = _seconds_per_bucket(buckets)
        hours = (sec / 3600.0) if sec else None
        if hours is not None:
            total_active_kwh = sum((v or 0.0) * hours for v in active_avgs)
            total_reactive_kvarh = sum((v or 0.0) * hours for v in reactive_avgs)
        else:
            total_active_kwh, total_reactive_kvarh = None, None

        # Expected-load baseline + band
        baseline_mean, baseline_sigma = _mean_and_stddev(load_pct_avgs)
        if baseline_mean is not None and baseline_sigma is not None:
            band_upper = baseline_mean + BAND_K_SIGMA * baseline_sigma
            band_lower = max(0.0, baseline_mean - BAND_K_SIGMA * baseline_sigma)
        else:
            band_upper = band_lower = None

        # Surge / Dip event counts
        if band_upper is not None and band_lower is not None:
            surge = sum(1 for v in load_pct_avgs if v is not None and v > band_upper)
            dip   = sum(1 for v in load_pct_avgs if v is not None and v < band_lower)
        else:
            surge = dip = 0

        return {
            'max_load_pct':         max_load_pct,
            'max_load_pct_at':      max_load_pct_at,
            'load_factor':          load_factor,
            'total_active_kwh':     total_active_kwh,
            'total_reactive_kvarh': total_reactive_kvarh,
            'hourly_avg_power_kw':  mean_active,
            'expected_load_pct':    baseline_mean,
            'expected_band_upper':  band_upper,
            'expected_band_lower':  band_lower,
            'surge_events_count':   surge,
            'dip_events_count':     dip,
            'bucket_count':         len(buckets),
            'band_k_sigma':         BAND_K_SIGMA,
        }
