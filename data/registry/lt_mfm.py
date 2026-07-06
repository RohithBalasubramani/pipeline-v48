"""data/registry/lt_mfm.py — the CANONICAL asset registry reader (CMD_V2's proven mapping), MIRROR-FIRST.

THE id-space is canonical `lt_mfm.id` (stable; what every lt_mfm_outgoing/incoming edge references). Reads go to the
LOCAL cmd_catalog mirror (`registry_*`, built by scripts/sync_neuract_registry.py) so no request-time read rides the
flaky :5433 tunnel; graceful fallback to live neuract ONLY when the mirror is absent. Time-series DATA reads are NOT
here — they stay on :5433 (this module is metadata only).

Concerns served (one accessor so the id-space cannot fork again):
  · registry_rows()  — one row per canonical asset: 320 lt_mfm meters (id = lt_mfm.id) + the asset-table-only meters
                       (pqm_*) at the non-colliding id range ASSET_ID_BASE+asset.id. Carries the authoritative class
                       codes (asset_type first — lt_mfm_type mis-types every DG MFM as lt_panel), the sync-stamped
                       table_exists (F11: 14 canonical rows point at ghost tables) and never_wired (0 device_mappings
                       rows — the data-driven signal that replaces the old `_sch` name-suffix hardcode, which would
                       also have wrongly dropped the LIVE gic_29 *_sch meters).
  · parent_ids()     — canonical ids with >=1 outgoing feeder edge (the aggregate/panel parents).
  · outgoing_edges() — one hop DOWN the feed topology: [(child_id, child_table)].
[user directives (c) mirror-local + (d) CMD_V2 semantics verbatim; AUDIT-3 id-space adoption]
"""
from data.db_client import q
from config.databases import CMD_CATALOG, DATA_DB, DATA_SCHEMA

ASSET_ID_BASE = 100000          # asset-table-only meters (pqm_*) live at ASSET_ID_BASE+asset.id — never collides with lt_mfm.id

_CACHE = {}


def _home():
    """(db, table_prefix) for canonical registry reads: the local mirror when present, else live neuract (fallback)."""
    if "home" in _CACHE:
        return _CACHE["home"]
    try:
        hit = q(CMD_CATALOG, "SELECT 1 FROM information_schema.tables WHERE table_name='registry_lt_mfm' LIMIT 1")
        home = (CMD_CATALOG, "registry_") if hit else (DATA_DB, f"{DATA_SCHEMA}.")
    except Exception:
        home = (DATA_DB, f"{DATA_SCHEMA}.")
    _CACHE["home"] = home
    return home


def _bool(v):
    return str(v).strip().lower() in ("t", "true", "1")


def registry_rows():
    """One dict per canonical asset, ordered by id:
    {id:int, name, table, mfm_type_id, load_group, asset_type_code, mfm_type_code, table_exists, never_wired}."""
    if "rows" in _CACHE:
        return _CACHE["rows"]
    db, p = _home()
    if p == "registry_":
        exists_expr, wired_expr = "m.table_exists", "m.never_wired"
        a_exists = f"EXISTS(SELECT 1 FROM {p}device_mappings d WHERE d.table_name=a.table_name)"
    else:  # live-neuract fallback: compute the sync-stamped flags inline
        exists_expr = ("EXISTS(SELECT 1 FROM information_schema.tables i "
                       f"WHERE i.table_schema='{DATA_SCHEMA}' AND i.table_name=m.table_name)")
        wired_expr = f"NOT EXISTS(SELECT 1 FROM {p}device_mappings d WHERE d.table_name=m.table_name)"
        a_exists = f"EXISTS(SELECT 1 FROM {p}device_mappings d WHERE d.table_name=a.table_name)"
    sql = (
        f"SELECT m.id, regexp_replace(m.name,'[[:cntrl:]]',' ','g'), m.table_name, m.mfm_type_id,"
        f"       regexp_replace(COALESCE(m.load_group,''),'[[:cntrl:]]',' ','g'),"
        f"       at.code, t.code, {exists_expr}, {wired_expr} "
        f"FROM {p}lt_mfm m "
        f"LEFT JOIN {p}lt_mfm_type t ON t.id = m.mfm_type_id "
        f"LEFT JOIN {p}asset a ON a.table_name = m.table_name "
        f"LEFT JOIN {p}asset_type at ON at.id = a.asset_type_id "
        f"UNION ALL "
        f"SELECT {ASSET_ID_BASE}+a.id, regexp_replace(a.name,'[[:cntrl:]]',' ','g'), a.table_name, NULL,"
        f"       regexp_replace(COALESCE(a.\"group\",''),'[[:cntrl:]]',' ','g'),"
        f"       at.code, NULL, {a_exists}, NOT {a_exists} "
        f"FROM {p}asset a "
        f"LEFT JOIN {p}asset_type at ON at.id = a.asset_type_id "
        f"WHERE a.table_name IS NOT NULL AND a.table_name <> '' "
        f"  AND a.table_name NOT IN (SELECT table_name FROM {p}lt_mfm) "
        f"ORDER BY 1"
    )
    rows = [{"id": int(r[0]), "name": r[1], "table": r[2] or None,
             "mfm_type_id": int(r[3]) if r[3] else None, "load_group": r[4] or None,
             "asset_type_code": r[5] or None, "mfm_type_code": r[6] or None,
             "table_exists": _bool(r[7]), "never_wired": _bool(r[8])} for r in q(db, sql)]
    _CACHE["rows"] = rows
    return rows


def parent_ids():
    """Canonical ids that fan out (>=1 outgoing feeder edge) — the aggregate/panel parents. fail-open to empty."""
    if "parents" in _CACHE:
        return _CACHE["parents"]
    db, p = _home()
    try:
        ids = {int(r[0]) for r in q(db, f"SELECT DISTINCT from_mfm_id FROM {p}lt_mfm_outgoing") if r and r[0]}
    except Exception:
        ids = set()
    _CACHE["parents"] = ids
    return ids


def outgoing_edges(ids):
    """One batched hop DOWN the feed side for canonical ids: [(child_id, child_table_or_None)] in edge order.
    lt_mfm_incoming is the verified EXACT mirror of outgoing (from=receiver, to=source) — we read outgoing only.
    fail-open to [] (a topology read failure honest-degrades to 'no children', never a crash)."""
    ids = [int(i) for i in (ids or [])]
    if not ids:
        return []
    db, p = _home()
    id_list = ",".join(str(i) for i in ids)
    try:
        rows = q(db, f"SELECT o.to_mfm_id, m.table_name FROM {p}lt_mfm_outgoing o "
                     f"JOIN {p}lt_mfm m ON m.id = o.to_mfm_id "
                     f"WHERE o.from_mfm_id IN ({id_list}) ORDER BY o.id")
    except Exception as e:
        import sys
        sys.stderr.write(f"[registry.lt_mfm] outgoing read failed ({str(e)[:80]}) — treating as no children\n")
        return []
    return [(int(r[0]), (r[1] or None)) for r in rows if r and r[0]]


def outgoing_feeders(mfm_id):
    """ONE panel's FROM-side feeders WITH display names: [{mfm_id, table_name, name}] (SLD / history fan-out shape).
    Same mirror-first edge source as outgoing_edges; [] on no id / no edges / read failure (honest-degrade)."""
    if mfm_id in (None, ""):
        return []
    db, p = _home()
    try:
        rows = q(db, f"SELECT o.to_mfm_id, m.table_name, m.name FROM {p}lt_mfm_outgoing o "
                     f"JOIN {p}lt_mfm m ON m.id = o.to_mfm_id "
                     f"WHERE o.from_mfm_id = {int(mfm_id)} ORDER BY o.to_mfm_id")
    except Exception:
        return []
    return [{"mfm_id": int(r[0]) if r[0] not in (None, "") else None,
             "table_name": r[1], "name": (r[2] or "").strip()} for r in rows if r and r[1]]
