"""config/validation.py — knobs for the NON-AI data-validation layer (Rule #1b). Edit here, not in validate/.

The on-failure POLICY is a DEFERRED decision (user: "we will decide later") — default 'annotate'
means the layer only attaches verdicts; it never drops/blocks. Flip to 'drop' or 'fail' later
without touching layer code.
"""
import os

from config.app_config import cfg
from config.databases import DATA_TS_COL

# --- data load ---
# ONE FACT, ONE KNOB: the data-table timestamp column is config.databases.DATA_TS_COL; validation.time_column (DB row /
# V48_TIME_COLUMN env) is only an explicit OVERRIDE. The two independent knobs (the structural cause of the stale-'ts'
# bug: editing one silently left the other half of the pipeline reading a different column) are unified here.
TIME_COLUMN = cfg("validation.time_column", os.environ.get("V48_TIME_COLUMN", DATA_TS_COL))
PROBE_ROWS = cfg("validation.probe_rows", int(os.environ.get("V48_VALIDATE_ROWS", "500")))   # rows pulled into pandas per asset

# --- data-quality thresholds (per basket column over the probe window) ---
MAX_NULL_RATE = cfg("validation.max_null_rate", float(os.environ.get("V48_MAX_NULL_RATE", "0.5")))    # > this -> fail (mostly empty)
WARN_NULL_RATE = cfg("validation.warn_null_rate", float(os.environ.get("V48_WARN_NULL_RATE", "0.1")))  # > this -> warn
MIN_ROWS_SERIES = cfg("validation.min_rows_series", int(os.environ.get("V48_MIN_ROWS_SERIES", "12")))   # a time-series leaf needs >= this many rows

# per-phase column suffixes (so payload arrays of ~3-4 can be matched to phase supply). Includes the compound real
# neuract forms (per-phase power/THD/deviation/raw-pf) the endswith matcher missed — supply.phase_cols undercounted
# ~10-of-25 and could emit a spurious 'thin phase supply' warn on a per-phase-power basket. [AUDIT-2 phase-suffixes]
PHASE_SUFFIXES = tuple(cfg("validation.phase_suffixes", [
    "_r", "_y", "_b", "_n", "_ry", "_yb", "_br", "_r_n", "_y_n", "_b_n", "_neutral",
    "_r_kw", "_y_kw", "_b_kw", "_r_kva", "_y_kva", "_b_kva", "_r_kvar", "_y_kvar", "_b_kvar",
    "_r_pct", "_y_pct", "_b_pct", "_r_deviation_pct", "_y_deviation_pct", "_b_deviation_pct",
    "_r_raw", "_y_raw", "_b_raw"]))

# plumbing/identity columns (NOT metric columns) — the ONE shared home for what col_dict skips and has_data excludes
# (the two sets had drifted: col_dict._SKIP vs has_data._PLUMBING). DB row validation.plumbing_columns overrides.
PLUMBING_COLUMNS = tuple(cfg("validation.plumbing_columns",
                             ["ts", "panel_id", "timestamp_utc", "id", "mfm_id",
                              "created_at", "updated_at", "device_id"]))

# event/flag column-name pattern (regex) — a TRUE 0/1 flag column (kind='event', no unit). Narrowed from
# `_compliance(_|$)` which over-matched the CONTINUOUS thd_compliance_i_avg/v_avg (% averages, real quality metrics)
# and biased the basket AI away from them with a wrong kind/unit. DB row validation.event_name_pattern overrides.
EVENT_NAME_PATTERN = str(cfg("validation.event_name_pattern",
                             r"(_event_active$|_status$|_compliance_ieee519$)"))

# a "small array" leaf (per-phase / few-category) is one whose length is <= this
SMALL_ARRAY_MAX = cfg("validation.small_array_max", int(os.environ.get("V48_SMALL_ARRAY_MAX", "8")))

# --- on-failure policy (DEFERRED — default annotate-only) ---
FAILURE_POLICY = cfg("validation.failure_policy", os.environ.get("V48_VALIDATE_POLICY", "annotate"))   # annotate | drop | fail
