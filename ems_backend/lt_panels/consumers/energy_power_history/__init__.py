"""Energy & Power History page — bucketed power/energy bars + load-anomaly KPIs.

Polymorphic history dispatcher: takes range = today | this_week | this_month
(and any other preset resolve_range understands) plus a sampling unit, returns
time-bucketed Active/Reactive power buckets and window-level KPIs (max %,
surge/dip event counts, load factor, expected-load baseline ± band).

Dispatcher URL pattern:
  ws/mfm/<int:mfm_id>/energy-power-history/?range=today&sampling=hour
"""
from .._history_base import _BaseHistoryDispatcher, StubHistoryStrategy
from .ups         import UpsEnergyPowerHistory


# UPS strategy is fully type-agnostic (only common cols + generic compute) —
# reuse it for transformer / LT / APFC. HT panel + sub_panel stay stubs
# until the simulator supports those types.
class TransformerEnergyPowerHistory(UpsEnergyPowerHistory): pass
class LtPanelEnergyPowerHistory(UpsEnergyPowerHistory):     pass
class ApfcEnergyPowerHistory(UpsEnergyPowerHistory):        pass
class PccPanelEnergyPowerHistory(UpsEnergyPowerHistory):    pass

class HtPanelEnergyPowerHistory(StubHistoryStrategy):       pass
class SubPanelEnergyPowerHistory(StubHistoryStrategy):      pass


class EnergyPowerHistoryDispatcher(_BaseHistoryDispatcher):
    PAGE_CODE = 'energy-power-history'
    STRATEGIES = {
        'lt_panel':    LtPanelEnergyPowerHistory,
        'transformer': TransformerEnergyPowerHistory,
        'ht_panel':    HtPanelEnergyPowerHistory,
        'ups':         UpsEnergyPowerHistory,
        'apfc':        ApfcEnergyPowerHistory,
        'sub_panel':   SubPanelEnergyPowerHistory,
        'pcc_panel':   PccPanelEnergyPowerHistory,
    }
