"""Tunable Power Quality thresholds + ordinal lookup (single source of truth).

Every deriver imports its limits from here so the whole PQ label surface
stays consistent with the seeded `*_config` table defaults
(v_thd_limit_pct = 5, i_thd_limit_pct = 8, pf_target = 0.95).
"""
from __future__ import annotations

# ── Tunable thresholds ──────────────────────────────────────────────────
V_THD_LIMIT_PCT       = 5.0   # IEEE 519 typical
I_THD_LIMIT_PCT       = 8.0   # IEEE 519 typical
PF_TARGET             = 0.95
V_UNBALANCE_WARN_PCT  = 2.0
THD_RISING_RATE_PCT_H = 5.0   # %-per-hour above this → Watch
SAG_SWELL_EVENT_HOT   = 10    # sag+swell over 24h above this → flag

ORDINAL = {1: '1st', 2: '2nd', 3: '3rd', 5: '5th', 7: '7th', 11: '11th', 13: '13th'}
