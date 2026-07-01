"""HT Transformer asset pages (type-specific).

Skeleton stub page. Replace `STRATEGY = StubStrategy` with a real
`BaseLiveStrategy` (or a history dispatcher) once the page spec lands.
"""
from .._base import StubStrategy, _BaseLiveDispatcher


class HtTransformerThermalDispatcher(_BaseLiveDispatcher):
    PAGE_CODE  = 'ht-transformer-thermal'
    ASSET_TYPE = 'ht_transformer'
    STRATEGY   = StubStrategy


__all__ = ['HtTransformerThermalDispatcher']
