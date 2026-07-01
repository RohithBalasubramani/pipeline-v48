"""Per-page WebSocket dispatchers for the `assets` app.

Architecture differs from lt_panels on purpose: lt_panels pages are GLOBAL
(every MFM type shares the same pages, varied by a per-type STRATEGIES map).
Asset pages are TYPE-SPECIFIC — each asset type has its own pages — so the
layout is type-first, and the per-type STRATEGIES map survives only on the
one shared page (`overview`).

Layout:

  consumers/
    _base.py        BaseLiveStrategy + _BaseLiveDispatcher (STRATEGY | STRATEGIES)
    _dispatch.py    resolve_category / lookup_strategy
    _notfound.py    catch-all 4404 dispatcher
    _serializer.py  JSON fallback

    overview/       OverviewDispatcher   ← SHARED page, STRATEGIES across types
    ups/            Battery&Autonomy · Source&Transfer · Output&Capacity (all wired)
    lt_transformer/ LtTransformerThermalDispatcher (stub)
    ht_transformer/ HtTransformerThermalDispatcher (stub)
    dg/             DgRuntimeDispatcher (stub)
"""
from .overview       import OverviewDispatcher
from .ups            import (
    UpsBatteryAutonomyDispatcher,
    UpsSourceTransferDispatcher,
    UpsOutputCapacityDispatcher,
)
from .lt_transformer import (
    LtTransformerThermalDispatcher,
    LtTransformerLossAnalysisDispatcher,
    LtTransformerUtilizationDispatcher,
)
from .ht_transformer import HtTransformerThermalDispatcher
from .dg             import DgRuntimeDispatcher

__all__ = [
    'OverviewDispatcher',
    'UpsBatteryAutonomyDispatcher',
    'UpsSourceTransferDispatcher',
    'UpsOutputCapacityDispatcher',
    'LtTransformerThermalDispatcher',
    'LtTransformerLossAnalysisDispatcher',
    'LtTransformerUtilizationDispatcher',
    'HtTransformerThermalDispatcher',
    'DgRuntimeDispatcher',
]
