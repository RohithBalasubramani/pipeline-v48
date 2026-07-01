"""derivations/nameplate.py — RATED/CONTRACT nameplate recoverers. The ONLY rated/contract/nominal source in V48 is
the editable cmd_catalog.asset_nameplate table (read via config.nameplates) — NO fabricated capacity, NO hardcoded
NAMEPLATE dict, NO 'live kW ÷ load%' back-out from phantom columns that never existed in neuract [RN-01, DS-10, DID-03].
  - rated_kva(asset_table) / feeder_rated_kw(asset_table) / section_contracts → config.nameplates.rated_kva by table.
  - ups_rated_kva → parsed from the asset NAME ('CL:<n>KVA') → works with no DB (the name travels with the asset).
  - nominal_voltage → voltage_avg/(1+dev%) → works on ANY db that kept voltage_avg + the deviation column.
A missing nameplate row honest-degrades the ONE affected slot (loading% denominator) — it never fabricates a rating."""
from __future__ import annotations

import re

from config import nameplates as _np

_UPS_KVA = re.compile(r"CL\s*:\s*(\d+(?:\.\d+)?)\s*KVA", re.I)


def feeder_rated_kw(asset_table, load_pct=None):
    """A feeder's rated active power (kW) from the nameplate rated kVA (× 0.8 pf-of-record when kW isn't stored). The
    ONLY source is asset_nameplate; `load_pct` is IGNORED (the old 'kW ÷ load%' back-out fabricated against a column
    neuract never had). None when the feeder has no nameplate row → honest-degrade. [DID-03]"""
    kva = _np.rated_kva(asset_table)
    if kva is None:
        return None
    return round(float(kva) * 0.8, 1)                       # rated kW ≈ rated kVA × nominal PF (0.8) — a stated convention


def rated_kva(asset_table):
    """Rated apparent capacity (kVA) — read straight from the editable asset_nameplate row. None when absent (never a
    fabricated default). [RN-01]"""
    v = _np.rated_kva(asset_table)
    try:
        return float(v) if v is not None and float(v) > 0 else None
    except (TypeError, ValueError):
        return None


def ups_rated_kva(name):
    """UPS rated apparent capacity parsed from the asset NAME ('UPS-01 CL:600KVA' → 600.0). Works on ANY db. None when
    the name has no CL:<n>KVA token (don't fabricate)."""
    m = _UPS_KVA.search(name or "")
    return float(m.group(1)) if m else None


def nominal_voltage(voltage_avg, voltage_deviation_pct):
    """L-N nominal voltage = avg ÷ (1 + deviation%). Works on ANY db that kept voltage_avg + the deviation column."""
    try:
        v = float(voltage_avg); dev = float(voltage_deviation_pct)
    except (TypeError, ValueError):
        return None
    denom = 1.0 + dev / 100.0
    return v / denom if denom > 0 else None


def section_id(name, role, type_code=None, asset_table=None):
    """Bucket a feeder into a heatmap section. PREFERS the real nameplate section (asset_nameplate.section, RN-05) when
    an asset_table is given; falls back to the name/role heuristic that MIRRORS the frontend mapper sectionIdFor."""
    if asset_table:
        _, sec = _np.role_section(asset_table)
        if sec:
            return sec
    role = (role or "").lower()
    name = (name or "").lower()
    t = (type_code or "").lower()
    if role == "incoming":
        return "incomers"
    if "ups" in name or "ups" in t:
        return "ups"
    if "bpdb" in name or "pdb" in name:
        return "bpdb"
    if "hhf" in name:
        return "hhf"
    return "ups"


def section_contracts(feeders):
    """Per-section sanctioned contract = Σ the section's feeders' nameplate rated_kw. Reads asset_nameplate per feeder
    table (the ONLY rated source). A feeder with no nameplate row is SKIPPED (honest-degrade, no fabricated number); if
    no feeder has a nameplate the whole map is {} (the card degrades). `feeders`: iterable of
    {name, role, type, table} (kw/load_pct kept for back-compat but IGNORED — no more phantom-column back-out)."""
    sums = {}
    for f in feeders or []:
        tbl = f.get("table") or f.get("asset_table") or f.get("table_name")
        rk = feeder_rated_kw(tbl)
        if rk is None:
            continue
        sec = section_id(f.get("name"), f.get("role"), f.get("type"), asset_table=tbl)
        sums[sec] = sums.get(sec, 0.0) + rk
    return {sec: round(total) for sec, total in sums.items() if total > 0}
