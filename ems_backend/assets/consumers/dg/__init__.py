"""Diesel Generator asset pages (type-specific).

Skeleton stub page. Replace `STRATEGY = StubStrategy` with a real
`BaseLiveStrategy` (or a history dispatcher) once the page spec lands.
"""
from .._base import StubStrategy, _BaseLiveDispatcher


class DgRuntimeDispatcher(_BaseLiveDispatcher):
    PAGE_CODE  = 'dg-runtime'
    ASSET_TYPE = 'dg'
    STRATEGY   = StubStrategy


__all__ = ['DgRuntimeDispatcher']
