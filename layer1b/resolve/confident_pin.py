"""layer1b/resolve/confident_pin.py — the confident single-meter pin path, WITH prefer-populated device de-dup. [DS-09, RN-06]

When the AI confidently names ONE meter, this finalizes the pin. The critical fix it owns: some physical devices are
DUPLICATED across two registry rows — a populated `<dev>_mfm` table and an empty `gic_28_*_jk` twin (DG-01 → dg_1_mfm
11464 rows vs gic_28_n1_dg_01_jk 0 rows; same for DG-2..6). If the AI pinned the EMPTY twin, the card blanks even
though the device IS logging. So confident_pin re-points the pin to the populated sibling of the SAME physical device,
keyed on device identity (class + unit number derived from the NAME, never the registry id — ids are off-by-one from
the unit number). Resolution is by TABLE membership of has_meaningful_data, never by row-id. [covers DS-09, RN-06]

If no populated duplicate exists, the original pin is kept and the caller's no_data gate decides render vs honest-blank.
"""
import re

from layer1b.resolve.asset_candidates import as_asset
from layer1b.resolve.has_data import tables_with_values


# ── device identity — the SAME physical device across DUPLICATE registry rows (different TABLES for one asset) ────────
# CRITICAL: identity must be conservative. A class+unit key like ('UPS',1) over-merges — UPS-01 repeats in EVERY GIC
# node (GIC-01-N3-UPS-01, GIC-17-N1-UPS-01, GIC-27-N1-UPS-01 are DISTINCT 600/160/60 kVA units), and AHU-1 exists in
# GIC-08 AND GIC-25. Merging those would collapse different physical devices → wrong data. The only documented true
# duplication (DS-09) is the DG family: a legacy `dg_N_mfm` table AND its `gic_28_nN_dg_0N_jk` twin are ONE physical
# diesel genset logged under two rows. We key device identity on the TABLE-NAME twin pattern, not the human name, so
# only genuine same-device duplicates merge. Add a new twin family here (one regex pair) to extend de-dup safely.
#
# Each entry: (family_key, compiled-regex over the neuract table_name → the device unit number as group 1). Two rows
# whose tables match the SAME family_key AND yield the SAME unit number are the same physical device.
_TWIN_FAMILIES = [
    ("DG", re.compile(r"^dg_(\d+)_mfm$", re.I)),                      # legacy DG meter table  → dg_1_mfm
    ("DG", re.compile(r"^gic_28_n\d+_dg_0*(\d+)_jk$", re.I)),         # gic-28 DG twin table   → gic_28_n1_dg_01_jk
]


def device_identity(name, cls, table=None):
    """(family, unit) identifying the physical device a registry row logs, keyed on the TABLE-NAME twin pattern (never
    the human name — unit numbers repeat across GIC nodes). Returns None when the row is not part of a known duplicate
    twin family, so distinct same-class devices are NEVER merged. `name`/`cls` are accepted for signature stability but
    identity is decided by `table` (falls back to name only if table is absent, matching the same table patterns)."""
    probe = table if table else name
    if not probe:
        return None
    for fam, rx in _TWIN_FAMILIES:
        m = rx.match(str(probe).strip())
        if m:
            return (fam, int(m.group(1)))
    return None


def _ident(row):
    """device_identity for an asset_candidates row [id,name,table,type,load_group,class,...]."""
    return device_identity(row[1], row[5], row[2] if len(row) > 2 else None)


def prefer_populated(cand_row, cands):
    """Given the AI-pinned candidate row and the full candidate list, return the row that should ACTUALLY be pinned:
    the populated duplicate of the same physical device if the pinned row's own table is empty. Resolves by table
    membership of tables_with_values (device identity), never by row-id. Returns `cand_row` unchanged when there is no
    duplicate or the pinned row is already populated. [DS-09 prefer-populated de-dup]"""
    ident = _ident(cand_row)
    if ident is None:
        return cand_row
    # all rows that are the SAME physical device (including the pin itself)
    dupes = [c for c in cands if _ident(c) == ident]
    if len(dupes) < 2:
        return cand_row
    # value-aware: which of the duplicate tables actually carry >= VALUE_MIN non-null metric columns
    live = tables_with_values([c[2] for c in dupes if c[2]])
    if cand_row[2] in live:                       # the pin is already the populated one — keep it
        return cand_row
    populated = [c for c in dupes if c[2] in live]
    return populated[0] if populated else cand_row


def confident_pin(cand_row, cands):
    """Finalize a confident single-meter resolution. Applies prefer-populated de-dup, then returns the resolved asset
    dict (as_asset). The caller runs the no_data gate on it (an all-dupes-empty device still yields no_data honestly).
    """
    row = prefer_populated(cand_row, cands)
    return as_asset(row)
