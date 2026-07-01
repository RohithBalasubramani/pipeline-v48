"""Current History page — date-bucketed phase currents + Neutral + KPIs."""
from .._history_base import _BaseHistoryDispatcher, StubHistoryStrategy
from .lt_panel    import LtPanelCurrentHistory
from .transformer import TransformerCurrentHistory
from .ups         import UpsCurrentHistory


class ApfcCurrentHistory(LtPanelCurrentHistory): pass


# ── Stubs — TODO: spec from user ─────────────────────────────────────────
class HtPanelCurrentHistory(StubHistoryStrategy):  pass
class SubPanelCurrentHistory(StubHistoryStrategy): pass


class CurrentHistoryDispatcher(_BaseHistoryDispatcher):
    PAGE_CODE = 'current-history'
    STRATEGIES = {
        'lt_panel':    LtPanelCurrentHistory,
        'transformer': TransformerCurrentHistory,
        'ht_panel':    HtPanelCurrentHistory,
        'ups':         UpsCurrentHistory,
        'apfc':        ApfcCurrentHistory,
        'sub_panel':   SubPanelCurrentHistory,
    }
