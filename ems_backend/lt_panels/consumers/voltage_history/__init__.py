"""Voltage History page — date-bucketed phase voltages + sag/swell + KPIs."""
from .._history_base import _BaseHistoryDispatcher, StubHistoryStrategy
from .lt_panel    import LtPanelVoltageHistory
from .transformer import TransformerVoltageHistory
from .ups         import UpsVoltageHistory


# APFC uses the same bucket math + Expected Range band as LT panels.
class ApfcVoltageHistory(LtPanelVoltageHistory): pass


# ── Stubs — TODO: spec from user ─────────────────────────────────────────
class HtPanelVoltageHistory(StubHistoryStrategy):  pass
class SubPanelVoltageHistory(StubHistoryStrategy): pass


class VoltageHistoryDispatcher(_BaseHistoryDispatcher):
    PAGE_CODE = 'voltage-history'
    STRATEGIES = {
        'lt_panel':    LtPanelVoltageHistory,
        'transformer': TransformerVoltageHistory,
        'ht_panel':    HtPanelVoltageHistory,
        'ups':         UpsVoltageHistory,
        'apfc':        ApfcVoltageHistory,
        'sub_panel':   SubPanelVoltageHistory,
    }
