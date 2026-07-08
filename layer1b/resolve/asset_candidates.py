"""layer1b/resolve/asset_candidates.py — the asset REGISTRY: one row per CANONICAL asset, sourced from the CMD_V2
canonical registry (cmd_catalog `registry_*` mirror, live-neuract fallback — data/registry/lt_mfm.py).

id IS canonical `lt_mfm.id` (asset-table-only pqm_* meters at ASSET_ID_BASE+asset.id) — the SAME id-space every
lt_mfm_outgoing/incoming edge, panel_members fan-out and ems_exec name-roster resolves against. This replaces the old
PRIVATE row_number() id-space over meta_data_version1, whose collisions mis-flagged all 4 PCC panels no_data,
greened 4 dead meters, and fanned foreign feeder subtrees into unrelated baskets (AUDIT-2/3, F9).

Row shape (contract): [id, name, table_name, mfm_type_id, load_group, class, has_data, has_feeders, never_wired,
                       table_exists].
  class       — authoritative first: asset_type.code (dg/ups/lt_transformer); else lt_mfm_type.code
                (apfc/transformer/ups — lt_panel is UNTRUSTED: it mis-types every DG MFM); else the name-pattern
                fallback vocabulary below (classes the canonical registry lacks: AHU/Chiller/Fan/Pump/...).
  has_data    — VALUE-aware: the table's latest row has >= VALUE_MIN non-null metric columns; OR the asset is a
                PANEL-granularity aggregate whose data legitimately comes from its feeders (config.asset_granularity —
                a non-Panel parent (Transformer/DG feeding downstream) is a SINGLE meter: its own table decides).
  has_feeders — canonical id ∈ lt_mfm_outgoing.from_mfm_id (correct by construction in the shared id-space).
  never_wired — ZERO device_mappings rows (sync-stamped): a ghost/stub row the picker greys honestly. Data-driven —
                replaces the `_sch` suffix hardcode (which also wrongly matched the LIVE gic_29 *_sch meters).
Rows whose table does not physically exist are kept (greyed) so the registry stays complete + honest.
"""
from config.asset_granularity import belongs_on_panel
from data.registry.lt_mfm import registry_rows, parent_ids, outgoing_edges
from layer1b.resolve.has_data import tables_with_data, tables_with_values

# authoritative class codes → the pipeline class vocabulary (aligned with class_from_subject's labels)
_ASSET_TYPE_CLASS = {"dg": "DG", "ups": "UPS", "lt_transformer": "Transformer"}
_MFM_TYPE_CLASS = {"apfc": "APFCR", "transformer": "Transformer", "ups": "UPS"}   # lt_panel untrusted (DG mis-typed)

# fallback vocabulary — equipment class from the table name (first match wins; order matters: UPS before Panel;
# Incomer BEFORE DG so 'gic_30_n2_11kv_ht_dg_incomer_se' is an Incomer, not a genset [hardening])
_NAME_CLASS = (
    (("ups",), "UPS"),
    (("transformer", "xformer", "_tfr"), "Transformer"),
    (("ahu",), "AHU"),
    (("air_washer", "airwasher"), "AirWasher"),
    (("chiller",), "Chiller"),
    (("apfc",), "APFCR"),
    (("pump",), "Pump"),
    (("compressor", "_comp"), "Compressor"),
    (("incomer", "_inc_", "incoming"), "Incomer"),
    (("dg_", "_dg_", "diesel", "generator"), "DG"),
    (("exhaust", "_fan", "fan_"), "Fan"),
    (("feeder",), "Feeder"),
    (("bpdb", "pdb", "pcc", "mcc", "mldb", "_db", "panel", "lamination", "packing", "curing"), "Panel"),
    (("electrical_room", "elec_room"), "ElectricalRoom"),
    (("spare",), "Spare"),
)


def _name_class(table):
    nm = (table or "").lower()
    for needles, cls in _NAME_CLASS:
        if any((nm.startswith(n) if n == "dg_" else n in nm) for n in needles):
            return cls
    return "Load"


def _class_of(r):
    """asset_type.code (authoritative) → trusted lt_mfm_type.code → name-pattern fallback. [AUDIT-3 class order]"""
    return (_ASSET_TYPE_CLASS.get(r.get("asset_type_code") or "")
            or _MFM_TYPE_CLASS.get(r.get("mfm_type_code") or "")
            or _name_class(r.get("table")))


def _alias_map():
    """{table: (aka, loc)} from the LOCAL equipment mirror (cmd_catalog.equipment.mfm via the data/equipment single
    door) — the HUMAN names a user actually says ('Feeder Tx-1 (PCC-1A)') beside the canonical registry names, plus a
    section/zone locator. ONE cached read; {} on knob-off ('equipment.alias.enabled') / outage — aliases are HINTS,
    the canonical name stays the only return contract, so a dead equipment schema changes nothing. [stream C]"""
    try:
        from config.app_config import cfg
        if str(cfg("equipment.alias.enabled", "on")).strip().lower() in ("off", "", "0", "false", "no", "none"):
            return {}
        from data.equipment.db import mfm_by_table
        out = {}
        for tbl, eq_rows in (mfm_by_table() or {}).items():
            names = [x.get("name") for x in eq_rows if x.get("name")]
            r0 = eq_rows[0] if eq_rows else {}
            loc = "/".join(v for v in ((r0.get("section") or ""), (r0.get("zone") or "")) if v)
            out[tbl] = ((names[0] if names else ""), loc)
        # PCC PANEL aliases [CMD_V2 LEGACY_PCC_PANEL_PATH_ALIASES → cmd_catalog.pcc_panel_alias]: the aggregate PCC
        # panels (PCC-Panel-1..4) have NO equipment.mfm row, so they carry no human alias — yet users type 'PCC-1A'.
        # Give each panel its 'PCC-NA' display alias so the AI resolves 'PCC-1A' → PCC-Panel-1 CONSISTENTLY instead of
        # surfacing a 4-panel picker. Keyed by the panel's neuract table via the registry id. [#3 fix]
        try:
            from data.db_client import q
            for tbl, aka in q("cmd_catalog",
                              "SELECT r.table_name, upper(a.alias) FROM pcc_panel_alias a "
                              "JOIN registry_lt_mfm r ON r.id=a.panel_mfm_id WHERE a.section='A'"):
                if tbl:
                    out[str(tbl)] = (str(aka), out.get(str(tbl), ("", ""))[1] or "PCC")
        except Exception:
            pass
        return out
    except Exception:
        return {}


def asset_candidates():
    """rows: [id, name, table_name, mfm_type_id, load_group, class, has_data, has_feeders, never_wired, table_exists,
    aka, loc] — canonical id-space, mirror-sourced (read-only). Only PHYSICALLY-EXISTING tables are probed for values
    (a ghost table in the batched probe would fail its whole chunk open). table_exists (index 9) is the sync-stamped
    GHOST flag: False for the 14 canonical rows that point at a table neuract never created (`_sch` disambiguation
    ghosts + dead `_se` rows) — such a row can NEVER render, so the resolver must never confidently pin it and the
    picker greys it. [P03] aka (index 10) / loc (index 11) are equipment-registry HUMAN-ALIAS + section/zone hints
    ('' when unmapped or the alias knob is off) — resolution hints only, the canonical name stays authoritative;
    every consumer indexes ≤9 or len-guards, so the two additive columns are shape-safe. [stream C]"""
    rows = registry_rows()
    parents = parent_ids()
    live = tables_with_values([r["table"] for r in rows if r["table"] and r["table_exists"]])
    amap = _alias_map()
    out = []
    for r in rows:
        cls = _class_of(r)
        has_feeders = r["id"] in parents
        # an aggregate whose data legitimately comes from feeders = PANEL-granularity class only; a non-Panel parent
        # is a single meter (its own table decides), so a ghost/_sch stub with edges is NOT greened by topology.
        has_data = (r["table"] in live) or (has_feeders and belongs_on_panel(True, cls))
        aka, loc = amap.get(r["table"]) or ("", "")
        if aka == r["name"]:
            aka = ""                                            # identical alias is pure noise
        out.append([str(r["id"]), r["name"], r["table"], str(r["mfm_type_id"] or ""), r["load_group"] or "",
                    cls, has_data, has_feeders, bool(r["never_wired"]), bool(r["table_exists"]), aka, loc])
    return out


def feeder_table(mfm_id):
    """A representative DATA-BEARING descendant's neuract table for an aggregate panel. The panel's OWN table is an
    empty stub (pcc_panel_N_feedbacks), but its cards reference the FEEDER metric schema (active_power_total_kw, …).
    1b builds the column basket from this so those metrics resolve instead of hallucinating. Drills DOWN the canonical
    topology BFS (mirror-first edges) because a panel's feeders may THEMSELVES be empty aggregates (transformer→PCC→
    leaf meter); every neuract meter shares the same schema family, so the first live descendant gives the right
    vocabulary. None for a leaf / a fully-dead subtree."""
    try:
        seen = {int(mfm_id)}
        frontier = [int(mfm_id)]
        for _ in range(6):                                   # depth guard (the hierarchy is ≤5 deep)
            if not frontier:
                break
            children = [(cid, t) for cid, t in outgoing_edges(frontier) if cid not in seen]
            if not children:
                break
            live = tables_with_data([t for _, t in children if t])
            for _, t in children:                            # prefer a DATA-bearing child at THIS level
                if t and t in live:
                    return t
            seen.update(cid for cid, _ in children)
            frontier = [cid for cid, _ in children]          # all empty here → drill deeper
    except Exception:
        pass
    return None


def as_asset(c):
    return {"mfm_id": int(c[0]), "name": c[1], "table": c[2] or None,
            "mfm_type_id": int(c[3]) if c[3] else None, "load_group": c[4] or None,
            "class": c[5] or None, "has_data": bool(c[6]) if len(c) > 6 else bool(c[2]),
            "has_feeders": bool(c[7]) if len(c) > 7 else False,
            "never_wired": bool(c[8]) if len(c) > 8 else False,
            "table_exists": bool(c[9]) if len(c) > 9 else bool(c[2]),
            "aka": (c[10] or None) if len(c) > 10 else None,    # equipment human alias (hint only) [stream C]
            "loc": (c[11] or None) if len(c) > 11 else None}    # equipment section/zone locator [stream C]
