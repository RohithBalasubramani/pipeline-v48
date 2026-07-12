"""layer2/swap/vocab.py — the DECLARED home of the swap action/origin string families [typing F5, 2026-07-12].

str CONSTANTS (+ Literal aliases), NOT enum.Enum — these strings cross the JSON emit contract, the DB replay store
and the FE; constants keep serialization byte-identical. Importers replace scattered literals 1:1. [atomic]"""
from typing import Literal

KEEP, SWAP = "keep", "swap"                                   # swap_decision.action (the AI's per-card verdict)
SwapAction = Literal["keep", "swap"]
ACTIONS = {KEEP, SWAP}

KEPT, SWAPPED, MUST_SWAP = "kept", "swapped", "must_swap"     # swap_decision.origin (how the final card got here)
SwapOrigin = Literal["kept", "swapped", "must_swap"]
ORIGINS = {KEPT, SWAPPED, MUST_SWAP}
