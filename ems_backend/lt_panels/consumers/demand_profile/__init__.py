"""Demand Profile page — date-bucketed power/demand bars + KPIs."""
from .._history_base import _BaseHistoryDispatcher, StubHistoryStrategy
from .lt_panel    import LtPanelDemandProfile
from .transformer import TransformerDemandProfile


# UPS + APFC + LT panel use the same demand-bucket math as transformer
# (LT panel one already exists). Just alias.
class UpsDemandProfile(LtPanelDemandProfile):     pass
class ApfcDemandProfile(LtPanelDemandProfile):    pass


# ── Stubs — TODO: spec from user ─────────────────────────────────────────
class HtPanelDemandProfile(StubHistoryStrategy):  pass
class SubPanelDemandProfile(StubHistoryStrategy): pass


class DemandProfileDispatcher(_BaseHistoryDispatcher):
    PAGE_CODE = 'demand-profile'
    STRATEGIES = {
        'lt_panel':    LtPanelDemandProfile,
        'transformer': TransformerDemandProfile,
        'ht_panel':    HtPanelDemandProfile,
        'ups':         UpsDemandProfile,
        'apfc':        ApfcDemandProfile,
        'sub_panel':   SubPanelDemandProfile,
    }
