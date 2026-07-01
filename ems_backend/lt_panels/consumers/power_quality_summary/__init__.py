"""Power Quality summary page — PQ / Voltage / Current Harmonic Stress KPIs.

For PCC Panel category this WS drives the entire 'Harmonics & PQ' page
(4 widgets: header KPIs, PQ priority list, fleet matrix, exposure share)
via an aggregate strategy. See pcc_panel.py.
"""
from .._base import _BaseLiveDispatcher, StubStrategy
from .lt_panel    import LtPanelPowerQualitySummary
from .transformer import TransformerPowerQualitySummary
from .pcc_panel   import PccPanelPowerQualitySummary
from .ups         import UpsPowerQualitySummary
from .apfc        import ApfcPowerQualitySummary


# ── Stubs — TODO: spec from user ─────────────────────────────────────────
class HtPanelPowerQualitySummary(StubStrategy): pass
class SubPanelPowerQualitySummary(StubStrategy): pass


class PowerQualitySummaryDispatcher(_BaseLiveDispatcher):
    PAGE_CODE = 'power-quality-summary'
    STRATEGIES = {
        'lt_panel':    LtPanelPowerQualitySummary,
        'transformer': TransformerPowerQualitySummary,
        'ht_panel':    HtPanelPowerQualitySummary,
        'ups':         UpsPowerQualitySummary,
        'apfc':        ApfcPowerQualitySummary,
        'sub_panel':   SubPanelPowerQualitySummary,
        'pcc_panel':   PccPanelPowerQualitySummary,
    }
