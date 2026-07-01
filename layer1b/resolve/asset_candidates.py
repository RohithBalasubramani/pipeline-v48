"""layer1b/resolve/asset_candidates.py — the asset REGISTRY: one row per migrated neuract data-table, built READ-ONLY
from the device registry `meta_data_version1` (app_devices ⋈ app_device_tables ⋈ app_gateways). The registry lives in
this adapter (code); nothing is created in the tunneled DB. Shape (unchanged contract): [id, name, table_name,
mfm_type_id, load_group, class].

  id          stable int = row_number() over (order by table) — a future ems_backend MFM seed uses the SAME ordering so
              mfm_id round-trips to the WS lookup ws/mfm/<id>/.
  name        the device's human name (app_devices.name, e.g. "GIC-01-N4-UPS-02 CL:600KVA").
  table_name  the neuract data table (app_device_tables.name, e.g. gic_01_n4_ups_02_cl_600kva) — what col_dict/ems read.
  load_group  the gateway (GIC node) name.
  class       equipment class inferred from the table name (UPS/Transformer/AHU/Panel/...).
chk_* shadow/duplicate tables are excluded.
"""
from data.db_client import q
from config.databases import LT_PANELS_DB, DATA_DB, DATA_SCHEMA, TOPOLOGY_OUTGOING
from layer1b.resolve.has_data import tables_with_data, tables_with_values

# equipment class from the neuract table name (first match wins; order matters — UPS before Panel, etc.)
_CLASS_SQL = """CASE
    WHEN r.nm LIKE '%ups%'                                                            THEN 'UPS'
    WHEN r.nm LIKE '%transformer%' OR r.nm LIKE '%xformer%' OR r.nm LIKE '%_tfr%'      THEN 'Transformer'
    WHEN r.nm LIKE '%ahu%'                                                             THEN 'AHU'
    WHEN r.nm LIKE '%air_washer%' OR r.nm LIKE '%airwasher%'                           THEN 'AirWasher'
    WHEN r.nm LIKE '%chiller%'                                                         THEN 'Chiller'
    WHEN r.nm LIKE '%apfc%'                                                            THEN 'APFCR'
    WHEN r.nm LIKE '%pump%'                                                            THEN 'Pump'
    WHEN r.nm LIKE '%compressor%' OR r.nm LIKE '%_comp%'                               THEN 'Compressor'
    WHEN r.nm LIKE 'dg_%' OR r.nm LIKE '%_dg_%' OR r.nm LIKE '%diesel%' OR r.nm LIKE '%generator%' THEN 'DG'
    WHEN r.nm LIKE '%exhaust%' OR r.nm LIKE '%_fan%' OR r.nm LIKE '%fan_%'             THEN 'Fan'
    WHEN r.nm LIKE '%incomer%' OR r.nm LIKE '%_inc_%' OR r.nm LIKE '%incoming%'        THEN 'Incomer'
    WHEN r.nm LIKE '%feeder%'                                                          THEN 'Feeder'
    WHEN r.nm LIKE '%bpdb%' OR r.nm LIKE '%pdb%' OR r.nm LIKE '%pcc%' OR r.nm LIKE '%mcc%'
      OR r.nm LIKE '%mldb%' OR r.nm LIKE '%_db%' OR r.nm LIKE '%panel%' OR r.nm LIKE '%lamination%'
      OR r.nm LIKE '%packing%' OR r.nm LIKE '%curing%'                                 THEN 'Panel'
    WHEN r.nm LIKE '%electrical_room%' OR r.nm LIKE '%elec_room%'                      THEN 'ElectricalRoom'
    WHEN r.nm LIKE '%spare%'                                                           THEN 'Spare'
    ELSE 'Load' END"""

_SQL = f"""
WITH reg AS (
    SELECT t.name AS tbl, lower(t.name) AS nm, d.name AS dev_name, d.gateway_id AS gw
    FROM app_device_tables t
    JOIN app_devices d ON d.id = t.device_id
    WHERE t.status = 'migrated' AND t.name NOT LIKE 'chk\\_%'
)
SELECT row_number() OVER (ORDER BY r.tbl) AS id,
       regexp_replace(r.dev_name, '[[:cntrl:]]', ' ', 'g') AS name,   -- strip CR/LF in source names (CSV-safe)
       r.tbl,
       '' AS mfm_type_id,
       regexp_replace(COALESCE(g.name, r.gw, ''), '[[:cntrl:]]', ' ', 'g') AS load_group,
       {_CLASS_SQL} AS class
FROM reg r
LEFT JOIN app_gateways g ON g.id = r.gw
ORDER BY r.tbl
"""


def asset_candidates():
    """rows: [id, name, table_name, mfm_type_id, load_group, class, has_data] — from meta_data_version1 (read-only).
    mfm_id is renumbered contiguous in table order so the ems_backend MFM seed (same order) round-trips ws/mfm/<id>/.
    Every existing asset is KEPT and TAGGED with has_data — VALUE-aware: the table has >=3 NON-NULL metric columns (NOT
    merely a row). A wired-but-silent meter (rows present, values all-null — e.g. HT-side transformers/incomers) is tagged
    has_data=False so the picker greys it and an explicit ask yields the NO-DATA outcome, instead of offering a green asset
    that renders nothing. fail-open (a check error tags has_data=True)."""
    neu = {r[0] for r in q(DATA_DB, f"SELECT table_name FROM information_schema.tables WHERE table_schema='{DATA_SCHEMA}'")}
    rows = [r for r in q(LT_PANELS_DB, _SQL) if r[2] in neu]
    out = [[str(i), r[1], r[2], r[3], r[4], r[5]] for i, r in enumerate(rows, 1)]
    live = tables_with_values([r[2] for r in rows])                  # VALUE-aware has_data (was tables_with_data = rows)
    parents = _parents_with_feeders()                                # aggregate panels: data comes from their feeders
    # DE-DUP: drop the `_sch` schema-stub tables (all 10 are empty; each device's metered twin is the `_se`/`_p1` table,
    # which IS offered). Filtered by SUFFIX (not name) so distinct same-named meters across/within GIC nodes (the four
    # "Solar Incomer-1", the "Spare N1/N2/…") are untouched. Filtering AFTER the row_number id assignment preserves every
    # surviving asset's mfm_id, so the ems_backend MFM seed / ws/mfm/<id> stays aligned. So "Transformer-01" resolves to
    # the metered _se variant, not the dead _sch stub.
    return [e + [e[2] in live or int(e[0]) in parents, int(e[0]) in parents]
            for e in out if not e[2].endswith("_sch")]               # +has_data(c6) +has_feeders(c7), minus _sch stubs


def _parents_with_feeders():
    """mfm_ids with ≥1 outgoing feeder = the panel→feeder topology the Sankey / energy-distribution aggregate is built
    from. An aggregate panel with an EMPTY own table (e.g. PCC-Panel-1) still has data via its feeders — so it must NOT
    be flagged NO-DATA. Table name from config/databases.py (TOPOLOGY_OUTGOING — swappable). fail-open."""
    try:
        return {int(r[0]) for r in q(DATA_DB, f'SELECT DISTINCT from_mfm_id FROM {DATA_SCHEMA}."{TOPOLOGY_OUTGOING}"')}
    except Exception:
        return set()


def feeder_table(mfm_id):
    """A representative DATA-BEARING descendant's neuract table for an aggregate panel. The panel's OWN table is an empty
    stub (pcc_panel_N_feedbacks), but its cards reference the FEEDER metric schema (active_power_total_kw, …). 1b builds
    the column basket from this so those metrics resolve instead of hallucinating. Drills DOWN the topology BFS because a
    panel's feeders may THEMSELVES be empty aggregates (transformer→PCC→leaf meter) — every neuract meter shares the same
    72-col schema, so the first live descendant gives the right vocabulary. None for a leaf / a fully-dead subtree."""
    try:
        seen = {int(mfm_id)}
        frontier = [int(mfm_id)]
        for _ in range(6):                                   # depth guard (the hierarchy is ≤5 deep)
            if not frontier:
                break
            ids = ",".join(str(i) for i in frontier)
            rows = q(DATA_DB, f'SELECT o.to_mfm_id, m.table_name FROM {DATA_SCHEMA}."{TOPOLOGY_OUTGOING}" o '
                              f'JOIN {DATA_SCHEMA}.lt_mfm m ON m.id=o.to_mfm_id '
                              f'WHERE o.from_mfm_id IN ({ids}) ORDER BY o.id')
            children = [(int(r[0]), r[1]) for r in rows if r[0] and int(r[0]) not in seen]
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
            "has_feeders": bool(c[7]) if len(c) > 7 else False}
