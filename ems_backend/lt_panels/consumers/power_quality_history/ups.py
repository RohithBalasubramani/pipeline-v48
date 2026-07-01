"""Power Quality History — UPS strategy.

Per-bucket aggregates (avg/min/max):
  - V-THD per phase + V-THD compliance avg
  - I-THD per phase + I-THD compliance avg
  - Individual harmonic orders (H3/H5/H7/H11/H13)
  - Power Factor, True PF, Displacement PF
  - Phase Angle, K-factor
  - voltage_avg (for the chart's Average Voltage legend tile)

Window-level KPIs returned in `kpis`:
  v_thd_avg / i_thd_avg          window mean of V/I THD averages
  v_thd_max / i_thd_max          window peak of THD compliance averages
  pf_avg / true_pf_avg           window mean
  pf_min / true_pf_min           window low — drives "PF drop" detection
  k_factor_max                   peak K-factor
  pf_displacement_gap_avg        window mean of (displacement − true)
  dominant_h5_pct / h7_pct       window means for the H5/H7 toggle pills
  ieee519_compliance_pct         % of buckets that passed IEEE 519
  bucket_count
"""
from .._history_base import BaseHistoryStrategy, argmax_bucket


def _mean(values):
    xs = [v for v in values if v is not None]
    if not xs:
        return None
    return sum(xs) / len(xs)


class UpsPowerQualityHistory(BaseHistoryStrategy):
    columns = [
        # Distortion & Harmonic Profile chart series
        'thd_voltage_r_pct', 'thd_voltage_y_pct', 'thd_voltage_b_pct',
        'thd_current_r_pct', 'thd_current_y_pct', 'thd_current_b_pct',
        'thd_compliance_v_avg', 'thd_compliance_i_avg',
        'harmonic_3rd_pct', 'harmonic_5th_pct', 'harmonic_7th_pct',
        'harmonic_11th_pct', 'harmonic_13th_pct',
        'voltage_avg',

        # Load Impact & Transformer Stress chart series
        'power_factor_total', 'kpi_true_pf', 'kpi_displacement_pf',
        'pf_displacement_gap',
        'phase_angle_deg',
        'k_factor', 'harmonic_loss_factor_fhl',
    ]
    extra_aggregates = {
        # `thd_compliance_ieee519` is TEXT in the simulator ('Pass'/'Fail').
        # Count rows that compare equal to 'Pass'.
        'ieee519_pass_buckets':
            "SUM(CASE WHEN thd_compliance_ieee519 = 'Pass' THEN 1 ELSE 0 END)",
        'sample_buckets':
            'SUM(CASE WHEN thd_compliance_ieee519 IS NOT NULL THEN 1 ELSE 0 END)',
    }

    def compute_kpis(self, buckets):
        if not buckets:
            return {
                'v_thd_avg': None, 'i_thd_avg': None,
                'v_thd_max': None, 'i_thd_max': None,
                'pf_avg': None,    'pf_min': None,    'pf_min_at': None,
                'true_pf_avg': None, 'true_pf_min': None,
                'k_factor_max': None, 'k_factor_max_at': None,
                'pf_displacement_gap_avg': None,
                'h5_avg': None, 'h7_avg': None,
                'ieee519_compliance_pct': None,
                'bucket_count': 0,
            }

        # V/I THD compliance averages (the chart's headline series)
        v_thd_avgs = [b.get('thd_compliance_v_avg_avg') for b in buckets]
        i_thd_avgs = [b.get('thd_compliance_i_avg_avg') for b in buckets]
        v_thd_max, _ = argmax_bucket(buckets, 'thd_compliance_v_avg_max', prefer='max')
        i_thd_max, _ = argmax_bucket(buckets, 'thd_compliance_i_avg_max', prefer='max')

        # PF window stats — important: PF "min" is the bad case
        pf_avg_avgs = [b.get('power_factor_total_avg') for b in buckets]
        pf_min, pf_min_at = argmax_bucket(buckets, 'power_factor_total_min', prefer='min')
        true_pf_avgs = [b.get('kpi_true_pf_avg') for b in buckets]
        true_pf_min, _ = argmax_bucket(buckets, 'kpi_true_pf_min', prefer='min')

        # K-factor window peak (worst case for transformer heating)
        k_max, k_max_at = argmax_bucket(buckets, 'k_factor_max', prefer='max')

        # PF displacement gap window mean
        gap_avgs = [b.get('pf_displacement_gap_avg') for b in buckets]

        # H5/H7 window means
        h5_avgs = [b.get('harmonic_5th_pct_avg') for b in buckets]
        h7_avgs = [b.get('harmonic_7th_pct_avg') for b in buckets]

        # IEEE 519 compliance % (boolean aggregate via extra_aggregates)
        passes = sum((b.get('ieee519_pass_buckets') or 0) for b in buckets)
        samples = sum((b.get('sample_buckets') or 0) for b in buckets)
        compliance_pct = (passes / samples * 100) if samples else None

        return {
            'v_thd_avg':               _mean(v_thd_avgs),
            'i_thd_avg':               _mean(i_thd_avgs),
            'v_thd_max':               v_thd_max,
            'i_thd_max':               i_thd_max,
            'pf_avg':                  _mean(pf_avg_avgs),
            'pf_min':                  pf_min,
            'pf_min_at':               pf_min_at,
            'true_pf_avg':             _mean(true_pf_avgs),
            'true_pf_min':             true_pf_min,
            'k_factor_max':            k_max,
            'k_factor_max_at':         k_max_at,
            'pf_displacement_gap_avg': _mean(gap_avgs),
            'h5_avg':                  _mean(h5_avgs),
            'h7_avg':                  _mean(h7_avgs),
            'ieee519_compliance_pct':  compliance_pct,
            'bucket_count':            len(buckets),
        }
