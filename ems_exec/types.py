"""ems_exec/types.py — annotation-only TypedDicts for the executor boundary [typing F2/F7]. total=False +
runtime-inert. The canonical `window` is a (start, end) tuple — normalize_window (executor/window_policy) is the ONE
union normalizer and build_ctx applies it, so ExecCtx.window never carries the raw FE dict form."""
from __future__ import annotations

from typing import Any, Optional, Tuple, TypedDict

Window = Optional[Tuple[Optional[str], Optional[str]]]   # (start_iso, end_iso) | None = full logged range


class ExecCtx(TypedDict, total=False):
    asset_table: str
    db_link: str
    window: Window
    mfm_id: int
    asset_name: str
    card_id: int
    page_key: str
    _agg_row: dict[str, Any]      # the ONE aggregate seam: a panel renderer's fleet-rolled superset row
