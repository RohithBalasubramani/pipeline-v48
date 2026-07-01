"""Voltage & Current page — live phase/aggregate values + status labels.

For PCC Panel category this WS drives the entire 'Voltage & Current' tab —
which is event-timeline focused, not live-phase focused (see pcc_panel.py).
"""
from .._base import _BaseLiveDispatcher, StubStrategy
from .lt_panel    import LtPanelVoltageCurrent
from .transformer import TransformerVoltageCurrent
from .pcc_panel   import PccPanelVoltageCurrent
from .ups         import UpsVoltageCurrent


# APFC sees the same phase voltages/currents as any column-row type.
class ApfcVoltageCurrent(LtPanelVoltageCurrent): pass


# ── Stubs — TODO: spec from user ─────────────────────────────────────────
class HtPanelVoltageCurrent(StubStrategy): pass
class SubPanelVoltageCurrent(StubStrategy): pass


class VoltageCurrentDispatcher(_BaseLiveDispatcher):
    PAGE_CODE = 'voltage-current'
    STRATEGIES = {
        'lt_panel':    LtPanelVoltageCurrent,
        'transformer': TransformerVoltageCurrent,
        'ht_panel':    HtPanelVoltageCurrent,
        'ups':         UpsVoltageCurrent,
        'apfc':        ApfcVoltageCurrent,
        'sub_panel':   SubPanelVoltageCurrent,
        'pcc_panel':   PccPanelVoltageCurrent,
    }
