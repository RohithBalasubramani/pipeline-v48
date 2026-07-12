"""config/swap.py — Layer-2 swap gate parameters + vocab. Tune here (or in the DB), not in layer2/swap/. [#13]

LAZY module attributes (PEP 562): each access re-reads cfg(), so a DB row edit + app_config.reload() reaches consumers
without a process restart (the old import-time binding pinned the boot-time value for the process life)."""
from config.app_config import cfg

# vague swap criteria that auto-reject (a swap must name a CONCRETE story-angle word)
_VAGUE_DEFAULT = [
    "better", "more relevant", "relevant", "nicer", "good fit", "best fit", "improved",
    "cleaner", "clearer", "more suitable", "suitable", "fits better", "more appropriate",
    "appropriate", "nice", "good", "great", "preferred", "stronger", "richer",
]

_LAZY = {
    "SIZE_TOLERANCE": lambda: cfg("swap.size_tolerance", 0.15),    # +/-15% card_grid_size pool
    "MIN_CONFIDENCE": lambda: cfg("swap.min_confidence", 0.90),    # accept a swap only at >= this confidence
    "SWAP_POOL_MAX":  lambda: cfg("swap.swap_pool_max", 6),        # closest-N offered swap candidates
    "VAGUE_CRITERIA": lambda: set(cfg("swap.vague_criteria", _VAGUE_DEFAULT)),
}


def __getattr__(name):
    if name in _LAZY:
        return _LAZY[name]()
    raise AttributeError(f"module 'config.swap' has no attribute {name!r}")
