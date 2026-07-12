"""lib/dict_merge.py — the pure recursive deep-merge helper for the layer2 pipeline process.

``deep_merge(base, over)`` is a verbatim port of backend2 ``core/resolver.py:21-28`` ``_merge`` — a DEEP recursive
merge where ``over`` wins at each LEAF, but nested dicts MERGE leaf-by-leaf instead of the whole sub-dict being
replaced. So a global ``pills.base`` survives a per-asset ``pills.anchor`` override, a baseline viewer ``config`` block
keeps its unspecified keys under a partial preset, etc.

This is the layer2-process twin of the legacy EMS service's lt_panels/lib/dict_merge.py: SAME pure function, but importable
WITHOUT that service's Django/psycopg package chain (that package's __init__ eagerly imports a DB connection module).
The 3D renderer (ems_exec/renderers/asset_3d.py) merges the global viewer baseline ⊕ the asset preset with this.

Pure function — NO I/O, NO DB, no imports beyond stdlib. Neither input is mutated (a fresh dict is built at every
level). ``None`` on either side is treated as an empty dict so callers can pass ``deep_merge(None, over)`` /
``deep_merge(base, None)`` freely. [atomic; one concern]
"""
from __future__ import annotations

from typing import Any


def deep_merge(base: dict | None, over: dict | None) -> dict[str, Any]:
    """DEEP recursive merge (``over`` wins at each leaf); nested dicts merge instead of replace.

    So a global ``pills.base`` survives a per-asset ``pills.anchor`` override, etc. (backend2 core/resolver.py:21-28
    ``_merge``.) Neither argument is mutated; ``None`` is treated as ``{}``.
    """
    out = dict(base or {})
    for k, v in (over or {}).items():
        bv = out.get(k)
        out[k] = deep_merge(bv, v) if isinstance(bv, dict) and isinstance(v, dict) else v
    return out
