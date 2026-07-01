"""Energy Distribution page — two flavours:

  Per-outgoing fan-out (lt_panel / transformer / ht_panel / ups / apfc) —
    streams live kW for each outgoing feeder. Tiny per-child strategy
    sets `power_column`.

  Parent-level aggregate (pcc_panel) — emits a single rich envelope
    (header KPIs + ranked consumers + Sankey + AI summary) over a
    switchable window (today / this_week / this_month). See pcc_panel.py.
"""
from .._fanout_base import _BaseFanOutDispatcher, BaseFanOutStrategy
from .pcc_panel import PccPanelEnergyDistribution


# ─────────────────────────────────────────────────────────────────────────────
# Per-type fan-out strategies
# ─────────────────────────────────────────────────────────────────────────────

class LtPanelEnergyDistribution(BaseFanOutStrategy):
    power_column = 'active_power_total_kw'


class TransformerEnergyDistribution(BaseFanOutStrategy):
    power_column = 'active_power_total_kw'


class HtPanelEnergyDistribution(BaseFanOutStrategy):
    power_column = 'active_power_total_kw'


class UpsEnergyDistribution(BaseFanOutStrategy):
    # TODO: confirm column name — UPS may expose output_active_power_kw
    power_column = 'active_power_total_kw'


class ApfcEnergyDistribution(BaseFanOutStrategy):
    power_column = 'active_power_total_kw'


class SubPanelEnergyDistribution(BaseFanOutStrategy):
    # TODO: spec — BPDB / PDB power column TBD
    power_column = 'active_power_total_kw'


# ─────────────────────────────────────────────────────────────────────────────
# Dispatcher
# ─────────────────────────────────────────────────────────────────────────────

class EnergyDistributionDispatcher(_BaseFanOutDispatcher):
    PAGE_CODE = 'energy-distribution'
    # Per-outgoing live-kW fan-out (used when the parent has no PARENT_STRATEGIES entry)
    STRATEGIES = {
        'lt_panel':    LtPanelEnergyDistribution,
        'transformer': TransformerEnergyDistribution,
        'ht_panel':    HtPanelEnergyDistribution,
        'ups':         UpsEnergyDistribution,
        'apfc':        ApfcEnergyDistribution,
        'sub_panel':   SubPanelEnergyDistribution,
    }
    # Parent-level aggregate strategies — checked FIRST. If the parent's
    # category has an entry here, the dispatcher uses the rich aggregate
    # envelope and skips per-outgoing fan-out.
    PARENT_STRATEGIES = {
        'pcc_panel': PccPanelEnergyDistribution,
    }
