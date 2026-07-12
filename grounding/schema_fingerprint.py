"""grounding/schema_fingerprint.py — classify a live neuract table into ONE schema FINGERPRINT by its EXACT column set.

THE PROBLEM (DS-03, DS-07): the neuract schema is NOT uniform. Five real shapes coexist and the standard `_p1` mapper
returns all-None on the others:
  · p1_72         — the 72-col standard feeder/UPS meter (has active_power_total_kw AND harmonic_5th_pct).
  · ng_se_jk_70   — the 70-col _ng/_se/_jk/_sch transformer/panel meter (power+energy, but NO harmonic_5th/7th/voltage-THD).
  · tm_ups_56     — the 56-col 600kVA-UPS meter with a totally different UPS naming (output_active_power_total_kw,
                     battery_backup_pct) — shares ONLY timestamp_utc with p1.
  · feedbacks_35  — the 35-col PCC-panel SCADA feedback table (breaker/relay/temp flags — bc_acb_on_fb, tf_1_winding_
                     temperature — ZERO power/energy columns).
  · sch_stub      — the honest FALLBACK: any table whose column set matches NONE of the four known fingerprints
                     (malformed / spare / stub tables, 2..31 cols). The routed mapper then honest-degrades every slot.

THE FIX (deterministic, no AI): read the table's REAL column set once, test the fingerprints in specificity order by a
small set of MARKER columns (declared in schema_slot_map — never hardcoded here beyond the discriminator identity), and
return the fingerprint key. This NAMES a schema — it never emits a fetched number.

Covers: DS-03, DS-07 (schema-vs-mapper), and feeds meaningful/metric_class/schema_route.
"""
from __future__ import annotations

from data.db_client import q
from config.databases import DATA_DB, DATA_SCHEMA

# the fingerprint keys, in the order schema_slot_map was seeded (db/seed_schema_and_endpoints.py FINGERPRINT_REPS).
P1_72 = "p1_72"
NG_SE_JK_70 = "ng_se_jk_70"
TM_UPS_56 = "tm_ups_56"
FEEDBACKS_35 = "feedbacks_35"
SCH_STUB = "sch_stub"                     # the honest fallback — matches none of the four known shapes

KNOWN = (P1_72, NG_SE_JK_70, TM_UPS_56, FEEDBACKS_35)

# MARKER columns that discriminate the four known fingerprints. These are IDENTITY markers (which physical column proves
# a shape), NOT policy thresholds — the full slot→column routing lives in cmd_catalog.schema_slot_map (config.schema_map).
# tm_ups is proven by its UPS-only naming; feedbacks by its breaker flag; p1 vs ng_se_jk split on the harmonic-5th column
# that ng/se/jk/sch tables structurally lack.
_MARK_UPS_POWER = "output_active_power_total_kw"     # tm_ups_56 only (UPS output naming)
_MARK_UPS_BATT = "battery_backup_pct"                # tm_ups_56 only
_MARK_BREAKER = "bc_acb_on_fb"                        # feedbacks_35 only (SCADA breaker flag)
_MARK_STD_POWER = "active_power_total_kw"             # p1_72 AND ng_se_jk_70 (standard MFM naming)
_MARK_HARMONIC5 = "harmonic_5th_pct"                 # p1_72 only — ng/se/jk/sch tables lack it

_CACHE: dict[str, str] = {}


def _esc(s):
    return str(s).replace("'", "''")


def real_table_cols(table):
    """The SET of real physical columns on a live neuract table (one information_schema read). {} for a missing table."""
    if not table:
        return set()
    rows = q(DATA_DB,
             "SELECT column_name FROM information_schema.columns "
             f"WHERE table_schema='{_esc(DATA_SCHEMA)}' AND table_name='{_esc(table)}'")
    return {r[0] for r in rows if r and r[0]}


def fingerprint(table):
    """Classify `table` → one of {p1_72, ng_se_jk_70, tm_ups_56, feedbacks_35, sch_stub}. Cached per process.

    Specificity order (most-specific first): UPS-naming → breaker-flag → standard-power (p1 vs ng_se_jk on harmonic_5th)
    → else the honest sch_stub fallback. A table matching none of the four is `sch_stub`, whose routed mapper blanks
    every slot with a reason rather than force-fitting the p1 map. NEVER raises — an absent/odd table is sch_stub.
    """
    if not table:
        return SCH_STUB
    if table in _CACHE:
        return _CACHE[table]
    try:
        cols = real_table_cols(table)
    except Exception:
        cols = set()                                  # fail-safe: unreadable schema → honest stub, never crash
    fp = _classify(cols)
    _CACHE[table] = fp
    return fp


def _classify(cols):
    """Pure column-set → fingerprint (extracted so a caller with a column set already in hand can reuse it)."""
    if _MARK_UPS_POWER in cols or _MARK_UPS_BATT in cols:
        return TM_UPS_56
    if _MARK_BREAKER in cols:
        return FEEDBACKS_35
    if _MARK_STD_POWER in cols:
        return P1_72 if _MARK_HARMONIC5 in cols else NG_SE_JK_70
    return SCH_STUB


def is_known(fp):
    """True when the fingerprint is one of the four routable shapes (feeds meaningful/route: sch_stub → honest-blank)."""
    return fp in KNOWN
