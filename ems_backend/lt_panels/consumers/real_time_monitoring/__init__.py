"""Real Time Monitoring page — Power & Energy + Voltage + Current."""
from .._base import _BaseLiveDispatcher, StubStrategy
from .lt_panel    import LtPanelRealTimeMonitoring
from .transformer import TransformerRealTimeMonitoring
from .pcc_panel   import PccPanelRealTimeMonitoring
from .ups         import UpsRealTimeMonitoring


# APFC: same RTM shape as LT panel (live power + L-N voltage + R/Y/B
# current + frequency). APFC-specific compensation telemetry surfaces
# on the PQ and E&P pages where it's meaningful.
class ApfcRealTimeMonitoring(LtPanelRealTimeMonitoring): pass


# ── Stubs — TODO: spec from user ─────────────────────────────────────────
class HtPanelRealTimeMonitoring(StubStrategy): pass
class SubPanelRealTimeMonitoring(StubStrategy): pass


class RealTimeMonitoringDispatcher(_BaseLiveDispatcher):
    PAGE_CODE = 'real-time-monitoring'
    STRATEGIES = {
        'lt_panel':    LtPanelRealTimeMonitoring,
        'transformer': TransformerRealTimeMonitoring,
        'ht_panel':    HtPanelRealTimeMonitoring,
        'ups':         UpsRealTimeMonitoring,
        'apfc':        ApfcRealTimeMonitoring,
        'sub_panel':   SubPanelRealTimeMonitoring,
        'pcc_panel':   PccPanelRealTimeMonitoring,
    }
