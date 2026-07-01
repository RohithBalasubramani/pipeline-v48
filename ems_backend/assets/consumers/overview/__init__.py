"""Overview page — the ONE page common to every asset type.

This is the only shared page, so it's the only one that keeps the
lt_panels-style per-type `STRATEGIES` map: one dispatcher, one endpoint
(`overview`), a strategy per asset type. Every other page is type-specific
and lives under its own type package (ups/, lt_transformer/, …).

Adding a type to the overview = add one entry to STRATEGIES + a strategy
module declaring its headline `columns`.
"""
from .._widgets_base import _BaseWidgetDispatcher
from .lt_transformer import LtTransformerOverview
from .ht_transformer import HtTransformerOverview
from .dg import DgOverview
from .ups import UpsOverview


class OverviewDispatcher(_BaseWidgetDispatcher):
    PAGE_CODE = 'overview'
    STRATEGIES = {
        'lt_transformer': LtTransformerOverview,
        'ht_transformer': HtTransformerOverview,
        'dg':             DgOverview,
        'ups':            UpsOverview,
    }
