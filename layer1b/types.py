"""layer1b/types.py — annotation-only TypedDicts for the 1b boundary [typing F2]. total=False + runtime-inert;
contract checks stay in layer1b/schema.validate_layer1b_output; the `how` vocabulary home is layer1b/how.py."""
from __future__ import annotations

from typing import Any, TypedDict


class Asset(TypedDict, total=False):
    name: str
    table: str                    # the neuract gic_* table (a.k.a. asset_table/table_name at other boundaries)
    mfm_id: int
    panel_id: int | None
    has_feeders: bool
    member_scope: str             # 'outgoing' | 'incomer' (layer1b/resolve/member_scope constants)
    asset_category: str


class ColumnBasket(TypedDict, total=False):
    columns: list[dict[str, Any]]     # the full self-described schema (column/unit/kind/has_data/rank/verdict)
    probable: list[dict[str, Any]]    # ranked relevant columns (+substitute_for / confidence / why)
    llm_failed: bool                  # basket AI never heard → logged floor only


class Layer1bOutput(TypedDict, total=False):
    asset: Asset | None
    how: str                          # layer1b/how.py vocabulary (AI / user-choice / no_data / ambiguous / …)
    candidate_list: list[dict[str, Any]]
    column_basket: ColumnBasket
    class_prior: str | None
    class_mismatch: bool
    llm_failed: bool
    contract_problems: list[str]
