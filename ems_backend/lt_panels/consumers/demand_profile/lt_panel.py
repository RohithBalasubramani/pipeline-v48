"""Demand Profile — LT panel strategy. Ported from legacy DemandProfileConsumer."""
from .._history_base import BaseHistoryStrategy, argmax_bucket


class LtPanelDemandProfile(BaseHistoryStrategy):
    columns = [
        'active_power_total_kw',
        'reactive_power_total_kvar',
        'demand_present_kw',
        'demand_avg_kva',
        'demand_max_kw',
    ]

    def compute_kpis(self, buckets):
        peak_demand, peak_demand_at = argmax_bucket(buckets, 'demand_max_kw_max', prefer='max')

        weighted_active, weighted_reactive, weight = 0.0, 0.0, 0
        for b in buckets:
            n = b.get('samples') or 0
            ap = b.get('active_power_total_kw_avg')
            rp = b.get('reactive_power_total_kvar_avg')
            if ap is not None and n:
                weighted_active += ap * n
            if rp is not None and n:
                weighted_reactive += rp * n
            if n:
                weight += n

        return {
            'peak_demand_kw':    peak_demand,
            'peak_demand_at':    peak_demand_at,
            'avg_active_kw':     (weighted_active / weight) if weight else None,
            'avg_reactive_kvar': (weighted_reactive / weight) if weight else None,
            'total_samples':     weight,
        }
