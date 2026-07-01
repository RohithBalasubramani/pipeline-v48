"""Overview page — widget-shaped per-(category, page) strategies."""
from .._overview_base import _BaseOverviewDispatcher, StubOverviewStrategy
from .transformer import TransformerOverview
from .pcc_panel   import PccPanelOverview
from .lt_panel    import LtPanelOverview
from .ups         import UpsOverview
from .apfc        import ApfcOverview


# ── Stubs — TODO: spec from user ─────────────────────────────────────────
class HtPanelOverview(StubOverviewStrategy): pass
class SubPanelOverview(StubOverviewStrategy): pass


class OverviewDispatcher(_BaseOverviewDispatcher):
    PAGE_CODE = 'overview'
    STRATEGIES = {
        'lt_panel':    LtPanelOverview,
        'transformer': TransformerOverview,
        'ht_panel':    HtPanelOverview,
        'ups':         UpsOverview,
        'apfc':        ApfcOverview,
        'sub_panel':   SubPanelOverview,
        'pcc_panel':   PccPanelOverview,
    }
