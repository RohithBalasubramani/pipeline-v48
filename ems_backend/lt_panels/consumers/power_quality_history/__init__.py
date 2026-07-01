"""Power Quality History — bucketed THD / harmonics / PF traces with range filter.

Polymorphic history dispatcher serving both charts on the UPS Power Quality
tab (and equivalent screens for other types):

  Distortion & Harmonic Profile     V-THD / I-THD per phase + H3/H5/H7/H11/H13
  Load Impact & Transformer Stress  Power Factor · True PF · Phase Angle · K-factor

Takes range = today | this_week | this_month (any resolve_range preset) and
sampling = hour | day. Frontend toggles V-THD/I-THD/H5/H7 and PF Health/
Angle/K-Stress are pure render-side selections — server returns all columns.

URL pattern:  ws/mfm/<int:mfm_id>/power-quality-history/?range=today&sampling=hour
"""
from .._history_base import _BaseHistoryDispatcher, StubHistoryStrategy
from .ups         import UpsPowerQualityHistory


# UPS PQ-history strategy is type-agnostic (only common cols + generic
# compute over THD / harmonics / PF / K-factor) — reuse for every type
# the simulator emits PQ data for. HT panel + sub_panel stay stubs.
class TransformerPowerQualityHistory(UpsPowerQualityHistory): pass
class LtPanelPowerQualityHistory(UpsPowerQualityHistory):     pass
class ApfcPowerQualityHistory(UpsPowerQualityHistory):        pass
class PccPanelPowerQualityHistory(UpsPowerQualityHistory):    pass

class HtPanelPowerQualityHistory(StubHistoryStrategy):        pass
class SubPanelPowerQualityHistory(StubHistoryStrategy):       pass


class PowerQualityHistoryDispatcher(_BaseHistoryDispatcher):
    PAGE_CODE = 'power-quality-history'
    STRATEGIES = {
        'lt_panel':    LtPanelPowerQualityHistory,
        'transformer': TransformerPowerQualityHistory,
        'ht_panel':    HtPanelPowerQualityHistory,
        'ups':         UpsPowerQualityHistory,
        'apfc':        ApfcPowerQualityHistory,
        'sub_panel':   SubPanelPowerQualityHistory,
        'pcc_panel':   PccPanelPowerQualityHistory,
    }
