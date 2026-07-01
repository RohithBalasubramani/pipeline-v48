"""config/swap.py — Layer-2 swap gate parameters + vocab. Tune here (or in the DB), not in layer2/swap/. [#13]"""
from config.app_config import cfg

SIZE_TOLERANCE = cfg("swap.size_tolerance", 0.15)    # +/-15% card_grid_size pool
MIN_CONFIDENCE = cfg("swap.min_confidence", 0.90)    # accept a swap only at >= this confidence
SWAP_POOL_MAX = cfg("swap.swap_pool_max", 6)         # closest-N offered swap candidates

# vague swap criteria that auto-reject (a swap must name a CONCRETE story-angle word)
VAGUE_CRITERIA = set(cfg("swap.vague_criteria", [
    "better", "more relevant", "relevant", "nicer", "good fit", "best fit", "improved",
    "cleaner", "clearer", "more suitable", "suitable", "fits better", "more appropriate",
    "appropriate", "nice", "good", "great", "preferred", "stronger", "richer",
]))
