"""layer1b/resolve/confident_pin.py — the confident single-meter pin path. [F5 correction of DS-09]

When the AI confidently names ONE meter, this finalizes the pin (as_asset). The caller runs the no_data gate on it, so
an empty meter still yields an honest no_data outcome (never a blank card).

NO TWIN DE-DUP (corrected 2026-07-04): the old DS-09 rule merged `dg_N_mfm` with its `gic_28_nN_dg_0N_jk` sibling as
"one physical genset logged twice" and silently re-pointed a pin from the empty sibling to the populated one. The
canonical `device_mappings` prove that assumption FALSE — every physical device carries its OWN device_id
('DG-3 MFM' = dev_...904, 'GIC-28-N3-DG-03 [Jackson]' = dev_...031 are DIFFERENT assets), and no device_id spans two
tables. Merging them mis-pinned 'DG-03 Jackson' to the legacy DG-3 meter (F5). So there is no twin merge: each registry
row is its own device. Homonyms (differently-named rows sharing a class+unit token) are handled up-front by the
name-collision gate in asset_resolve, which surfaces the picker instead of confidently pinning either. `device_identity`
/ `_ident` are retained (returning None) as a stable no-op seam: if a GENUINE same-device-two-tables duplication is ever
proven from device_mappings, wire it here (keyed on device_id, never a name pattern).
"""


def device_identity(name, cls, table=None):
    """Physical-device identity for de-dup. Returns None: the canonical device registry has NO true twins (every device
    has its own device_id, no device_id spans two tables), so no two registry rows are the same physical device. Kept as
    a stable seam — a proven device_id-keyed duplication would return a shared key here."""
    return None


def _ident(row):
    """device_identity for an asset_candidates row [id,name,table,...] — always None (no twin de-dup). [F5]"""
    return device_identity(row[1], row[5] if len(row) > 5 else None, row[2] if len(row) > 2 else None)


def confident_pin(cand_row, cands):
    """Finalize a confident single-meter resolution: the resolved asset dict (as_asset). No twin re-point — the pinned
    row IS the device. The caller's no_data gate decides render vs honest-blank."""
    from layer1b.resolve.asset_candidates import as_asset
    return as_asset(cand_row)
