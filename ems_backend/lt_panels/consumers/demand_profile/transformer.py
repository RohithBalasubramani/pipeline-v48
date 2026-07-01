"""Demand Profile — Transformer strategy.

Drives the "Power Energy Analysis" bar chart on the Transformer Energy & Power
page (Active/Reactive bars per hour + Hourly Average line; Demand toggle).

Column-tolerant fetch silently pads None for unconfirmed names below.
"""
from .._history_base import BaseHistoryStrategy, argmax_bucket


class TransformerDemandProfile(BaseHistoryStrategy):
    columns = [
        # Active/Reactive bars
        'active_power_total_kw',
        'reactive_power_total_kvar',
        # Demand line (toggle: Active Reactive | Demand)
        'demand_present_kw',         # TODO: confirm column on transformer rows
        'demand_avg_kva',            # TODO
        'demand_max_kw',             # TODO
        # Reference markers (Rated 425 kW, Contracted 415 kW on the chart)
        'rated_power_kw',            # TODO — drives "Rated 425 kW" line
        'contracted_power_kw',       # TODO — drives "Contracted 415 kW" line
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

        last = buckets[-1] if buckets else {}
        return {
            'peak_demand_kw':    peak_demand,
            'peak_demand_at':    peak_demand_at,
            'avg_active_kw':     (weighted_active / weight) if weight else None,
            'avg_reactive_kvar': (weighted_reactive / weight) if weight else None,
            # Reference markers — surface as KPIs so frontend doesn't have to dig
            'rated_kw':          last.get('rated_power_kw_max'),
            'contracted_kw':     last.get('contracted_power_kw_max'),
            'total_samples':     weight,
        }
