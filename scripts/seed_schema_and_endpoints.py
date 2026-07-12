#!/usr/bin/env python3
"""seed_schema_and_endpoints — DATA-DRIVEN seed for cmd_catalog.schema_slot_map.

Both are derived from live truth, not hand-typed:
  · schema_slot_map — for each schema FINGERPRINT (p1_72 / tm_ups_56 / feedbacks_35 / ng_se_jk_70 / sch_stub_3) we take a
    REPRESENTATIVE neuract table, read its actual columns from information_schema, and map each logical SLOT to the real
    column that is PRESENT (missing → column_name='' so the routed mapper honest-degrades, DS-03/07). The slot→column
    intent + unit + quantity is the editable policy; presence is verified against the live schema.
  · endpoint_policy — for each of the 9 EMS pages × resolver_scope (single_asset / panel_aggregate) we record the
    fetch endpoint (from endpoint_registry, the single source of truth) + the frame shape the card's fill mapper
    reads (queue for single-asset live, widgets for panel-aggregate, buckets for history) + is_history (ER-1/2/4/7).

Run (pyenv 3.11 or any python with the pipeline on sys.path):
    python3 scripts/seed_schema_and_endpoints.py
Idempotent: TRUNCATE + re-insert each table.
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # → pipeline_v48
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from data.db_client import q                                          # noqa: E402
from layer2.emit.instructions import endpoint_registry as EP                  # noqa: E402


# ── the logical SLOT → (unit, quantity, per-fingerprint candidate columns) intent ────────────────────────────────
# The candidate list is tried in order against the real columns; the first PRESENT one fills the slot (else '').
# This is the editable policy; column PRESENCE is verified live so we never map a slot to an absent column.
SLOTS = [
    # slot,                    unit,   quantity,          candidates-by-preference
    ("active_power_total_kw",  "kW",   "active_power",    ["active_power_total_kw", "output_active_power_total_kw", "input_active_power_total_kw"]),
    ("apparent_power_total_kva","kVA", "apparent_power",  ["apparent_power_total_kva", "nominal_output_apparent_kva"]),
    ("reactive_power_total_kvar","kVAR","reactive_power", ["reactive_power_total_kvar"]),
    ("energy_import_kwh",      "kWh",  "energy",          ["active_energy_import_kwh"]),
    ("energy_export_kwh",      "kWh",  "energy",          ["active_energy_export_kwh"]),
    ("reactive_energy_kvarh",  "kVARh","energy",          ["reactive_energy_import_kvarh"]),
    ("voltage_ll_avg",         "V",    "voltage",         ["voltage_ll_avg", "voltage_avg", "output_voltage_r", "nominal_output_voltage"]),
    ("voltage_r",              "V",    "voltage",         ["voltage_r_n", "output_voltage_r", "input_voltage_r"]),
    ("voltage_y",              "V",    "voltage",         ["voltage_y_n", "output_voltage_y", "input_voltage_y"]),
    ("voltage_b",              "V",    "voltage",         ["voltage_b_n", "output_voltage_b", "input_voltage_b"]),
    ("current_avg",            "A",    "current",         ["current_avg", "output_current_r", "input_current_r"]),
    ("current_r",              "A",    "current",         ["current_r", "output_current_r", "input_current_r"]),
    ("current_y",              "A",    "current",         ["current_y", "output_current_y", "input_current_y"]),
    ("current_b",              "A",    "current",         ["current_b", "output_current_b", "input_current_b"]),
    ("current_neutral",        "A",    "current",         ["current_neutral", "output_current_neutral"]),
    ("power_factor_total",     "pf",   "pf",              ["power_factor_total", "load_power_factor_pct"]),
    ("frequency_hz",           "Hz",   "frequency",       ["frequency_hz", "output_freq_hz", "input_freq_hz"]),
    ("thd_current_r_pct",      "pct",  "thd",             ["thd_current_r_pct"]),
    ("thd_current_y_pct",      "pct",  "thd",             ["thd_current_y_pct"]),
    ("thd_current_b_pct",      "pct",  "thd",             ["thd_current_b_pct"]),
    ("thd_voltage_r_pct",      "pct",  "thd",             ["thd_voltage_r_pct"]),
    ("thd_compliance_ieee519", "bool", "thd",             ["thd_compliance_ieee519"]),
    ("ups_load_pct",           "pct",  "loading",         ["output_load_r_pct", "load_power_factor_pct"]),
    ("battery_backup_pct",     "pct",  "battery",         ["battery_backup_pct"]),
    ("ups_mode",               "enum", "status",          ["ups_mode"]),
    ("breaker_on_fb",          "bool", "breaker",         ["bc_acb_on_fb", "tf_inc_1_acb_on_fb"]),
    ("winding_temp_c",         "degC", "temperature",     ["tf_1_winding_temperature"]),
]

# fingerprint → a representative neuract meter table to read columns from (verified to exist live). The 4 REAL meter
# schema families: p1_72 (185 tables), ng_se_jk_70 (the _ng/_se/_jk/_sch 70-col family, 111 tables), tm_ups_56 (12),
# feedbacks_35 (8). The 3-col tables (asset_coupler/asset_incoming/…) are Django topology joins, NOT meter data → excluded.
FINGERPRINT_REPS = {
    "p1_72":        "gic_01_n3_ups_01_p1",
    "tm_ups_56":    "gic_17_n1_600_kva_ups_01_tm",
    "feedbacks_35": "pcc_panel_1_feedbacks",
    "ng_se_jk_70":  "gic_15_n3_pcc_01_transformer_01_se",
}


def _cols(table):
    rows = q("target_version1",
             "SELECT column_name FROM information_schema.columns "
             f"WHERE table_schema='neuract' AND table_name='{table}'")
    return {r[0] for r in rows if r}


def seed_schema_slot_map():
    q("cmd_catalog", "TRUNCATE schema_slot_map")
    vals = []
    for fp, rep in FINGERPRINT_REPS.items():
        present = _cols(rep)
        if not present:
            sys.stderr.write(f"[warn] representative table {rep} for {fp} has no columns — skipping\n")
            continue
        for slot, unit, quantity, cands in SLOTS:
            col = next((c for c in cands if c in present), "")     # first present candidate, else '' (slot absent)
            vals.append(f"('{fp}','{slot}','{col}','{unit}','{quantity}')")
    q("cmd_catalog",
      "INSERT INTO schema_slot_map (fingerprint, slot, column_name, unit, quantity) VALUES "
      + ",".join(vals))
    return len(vals)




# seed_endpoint_policy RETIRED 2026-07-12 (unused-code audit): cmd_catalog.endpoint_policy never had a live
# reader (layer2/emit/instructions/endpoint_registry.PAGES is the deliberate anti-drift source) and the table
# was DROPPED (db/retire_unused_tables_20260712.sql; snapshot archive/db_snapshots_20260712/endpoint_policy.sql).


if __name__ == "__main__":
    n1 = seed_schema_slot_map()
    print(f"schema_slot_map: {n1} rows ({len(FINGERPRINT_REPS)} fingerprints x {len(SLOTS)} slots)")
