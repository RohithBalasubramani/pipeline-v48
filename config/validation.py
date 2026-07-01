"""config/validation.py — knobs for the NON-AI data-validation layer (Rule #1b). Edit here, not in validate/.

The on-failure POLICY is a DEFERRED decision (user: "we will decide later") — default 'annotate'
means the layer only attaches verdicts; it never drops/blocks. Flip to 'drop' or 'fail' later
without touching layer code.
"""
import os

from config.app_config import cfg

# --- data load ---
TIME_COLUMN = "ts"                                              # lt_panels row timestamp column
PROBE_ROWS = cfg("validation.probe_rows", int(os.environ.get("V48_VALIDATE_ROWS", "500")))   # rows pulled into pandas per asset

# --- data-quality thresholds (per basket column over the probe window) ---
MAX_NULL_RATE = cfg("validation.max_null_rate", float(os.environ.get("V48_MAX_NULL_RATE", "0.5")))    # > this -> fail (mostly empty)
WARN_NULL_RATE = cfg("validation.warn_null_rate", float(os.environ.get("V48_WARN_NULL_RATE", "0.1")))  # > this -> warn
MIN_ROWS_SERIES = cfg("validation.min_rows_series", int(os.environ.get("V48_MIN_ROWS_SERIES", "12")))   # a time-series leaf needs >= this many rows

# per-phase column suffixes (so payload arrays of ~3-4 can be matched to phase supply)
PHASE_SUFFIXES = tuple(cfg("validation.phase_suffixes", ["_r", "_y", "_b", "_n", "_ry", "_yb", "_br", "_r_n", "_y_n", "_b_n", "_neutral"]))

# a "small array" leaf (per-phase / few-category) is one whose length is <= this
SMALL_ARRAY_MAX = cfg("validation.small_array_max", int(os.environ.get("V48_SMALL_ARRAY_MAX", "8")))

# --- on-failure policy (DEFERRED — default annotate-only) ---
FAILURE_POLICY = cfg("validation.failure_policy", os.environ.get("V48_VALIDATE_POLICY", "annotate"))   # annotate | drop | fail
