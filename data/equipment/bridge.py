"""data/equipment/bridge.py — the table_name BRIDGE + the per-row IDENTITY GATE over the local equipment schema.

equipment.mfm.id is a DIFFERENT id space from canonical lt_mfm.id (eq 13 'Feeder Tx-1 (PCC-1A)' =
gic_15_n3_pcc_01_transformer_01_se = canonical 171) — the ONLY safe bridge is table_name, and a duplicated table_name
(the 18 dual-view twin groups) makes a row un-bridgeable for per-meter facts (honest skip; aliases still served).

IDENTITY GATE (fatal-3 fix): equipment.mfm.equipment_id/reference_id have MIXED semantics — equipment_id sometimes
names the meter's OWN unit ('UPS-07 (600KVA)' -> UPS-07) and sometimes the HOSTING PANEL ('AHU Panel-11' -> PCC-4A).
identity_node() accepts a hop ONLY when the meter name verifies against the node name, so a bay meter can never claim
its hosting panel's identity (and feeds_fed_by can never state PCC-2A's fan-out as an AHU meter's own).

Fail-open by package contract: every public fn returns None/[]/{} on miss / dup / DB error — never raises; failures
are never cached (data/equipment/db.py retries next call). UTF-8 rule: no raw row text on stdout.  [stream A]
"""
import re
import sys

from data.equipment import db as _db

_CACHE = {}


# ── alias normalization (1b parity) ─────────────────────────────────────────────────────────────────────────────────
def _norm_alias(s):
    """Normalized alias key. PINNED PARITY with layer1b/resolve/asset_resolve._norm (space/punctuation/case-insensitive:
    'PCC Panel 2 A' == 'pcc panel 2a' == 'PCC-Panel-2A') so an alias tier can never match differently than the
    canonical-name tier it sits behind."""
    return re.sub(r"[^a-z0-9]+", "", str(s).lower())


# ── the bridge ──────────────────────────────────────────────────────────────────────────────────────────────────────
def eq_row_for_table(table_name):
    """The UNIQUE equipment.mfm row for a canonical table_name -> {eq_mfm_id, name, role, section, zone, load_profile,
    asset_category, rated_capacity_kva, energy_direction, energy_scale, power_scale, equipment_id, reference_id,
    data_source_id}. None on miss / any of the dup-table twin groups / DB error. Never raises."""
    try:
        row = _db.unique_mfm_row(table_name)
        if not row:
            return None
        out = dict(row)
        out["eq_mfm_id"] = _int(out.pop("id", None))
        for k in ("equipment_id", "reference_id", "data_source_id"):
            out[k] = _int(out.get(k))
        out.pop("table_name", None)
        return out
    except Exception:
        return None


def aliases_for_table(table_name):
    """ALL equipment.mfm names sharing this table (dup twins INCLUDED — N aliases -> 1 canonical row); [] on miss."""
    try:
        rows = _db.mfm_by_table().get(table_name) or []
        return [r["name"] for r in rows if r.get("name")]
    except Exception:
        return []


def alias_index():
    """{normalized-alias: [table_name, ...]} over every equipment.mfm name. len(v) > 1 == a collision key (the caller
    MUST resolve those as ambiguous — e.g. the 4 cross-GIC 'Solar Incomer-1' rows). {} on DB error (not cached)."""
    try:
        if "alias_index" in _CACHE:
            return _CACHE["alias_index"]
        by_table = _db.mfm_by_table()
        if not by_table:
            return {}
        idx = {}
        for tbl, rows in by_table.items():
            for r in rows:
                key = _norm_alias(r.get("name") or "")
                if not key:
                    continue
                hit = idx.setdefault(key, [])
                if tbl not in hit:
                    hit.append(tbl)
        _CACHE["alias_index"] = idx
        return idx
    except Exception:
        return {}


# ── the identity gate ───────────────────────────────────────────────────────────────────────────────────────────────
def _identity_tokens(name):
    """The gate's normalized token list: strip parentheticals, lowercase, non-alnum -> space, de-zero-pad pure digit
    tokens ('AHU-09' -> ['ahu','9'])."""
    s = re.sub(r"\([^)]*\)", " ", str(name or ""))
    s = re.sub(r"[^a-z0-9]+", " ", s.lower())
    toks = []
    for t in s.split():
        if t.isdigit():
            t = t.lstrip("0") or "0"
        toks.append(t)
    return toks


def _name_verified(meter_name, node_name):
    """True iff the normalized token lists are equal OR one token SET is a subset of the other (either direction).
    Verifies 'UPS-07 (600KVA)'~'UPS-07', 'AHU Panel-11'~'AHU-11', 'AHU-9 South'~'AHU-09', and — PINNED INTENDED
    (round-2 improvement 5) — the '<node> incomer/outgoing' qualifier shapes ('UPS-07 incomer'~'UPS-07'). Rejects the
    hosting-panel mis-pointers ('AHU Panel-11'~'PCC-4A') and abbreviation misses ('AW Exhaust-05'~'Air Washer
    Exhaust-05' -> the 'aw' vs 'air washer' tokens never subset)."""
    a, b = _identity_tokens(meter_name), _identity_tokens(node_name)
    if not a or not b:
        return False
    if a == b:
        return True
    sa, sb = set(a), set(b)
    return sa <= sb or sb <= sa


def _nodes():
    """{equipment.equipment.id(int): {node_id, name, key, distribution_panel, metered, group, asset_type_code,
    panel_type_code}} — built once per process; {} for THIS call on DB error (failure NOT cached)."""
    if "nodes" in _CACHE:
        return _CACHE["nodes"]
    try:
        rows = _db.eq_q(
            'SELECT e.id, e.name, e.key, e.distribution_panel, e.metered, e."group", at.code, pt.code '
            "FROM equipment.equipment e "
            "LEFT JOIN equipment.core_assettype at ON at.id = e.asset_type_id "
            "LEFT JOIN equipment.core_paneltype pt ON pt.id = e.panel_type_id"
        )
    except Exception as e:  # noqa: BLE001 — fail-open by contract
        sys.stderr.write("[equipment.bridge] nodes read failed (%s); returning {} (not cached)\n" % type(e).__name__)
        return {}
    nodes = {}
    for r in rows:
        nid = _int(r[0])
        if nid is None:
            continue
        nodes[nid] = {
            "node_id": nid, "name": r[1] or None, "key": r[2] or None,
            "distribution_panel": _bool(r[3]), "metered": _bool(r[4]), "group": r[5] or None,
            "asset_type_code": r[6] or None, "panel_type_code": r[7] or None,
        }
    _CACHE["nodes"] = nodes
    return nodes


def identity_node(table_name):
    """THE PER-ROW IDENTITY GATE: the meter's OWN equipment.equipment node, resolved equipment_id-FIRST (the measured
    device) then reference_id, each hop accepted ONLY when the name-similarity check passes (_name_verified). Returns
    {node_id, via: 'equipment'|'reference', name, key, distribution_panel, metered, group, asset_type_code,
    panel_type_code}; None when neither side verifies (honest — never the hosting panel's identity), on a dup-table
    twin, or on DB error. Never raises."""
    try:
        row = _db.unique_mfm_row(table_name)
        if not row:
            return None
        nodes = _nodes()
        if not nodes:
            return None
        for via, fk in (("equipment", "equipment_id"), ("reference", "reference_id")):
            node = nodes.get(_int(row.get(fk)))
            if node and _name_verified(row.get("name"), node.get("name")):
                out = dict(node)
                out["via"] = via
                return out
        return None
    except Exception:
        return None


# ── node-level feed facts ───────────────────────────────────────────────────────────────────────────────────────────
def _feed_edges():
    """[(source_id, target_id)] over equipment.feeder kind='feed' ONLY (the 2 couplers excluded), in edge-id order.
    [] for THIS call on DB error (failure NOT cached)."""
    if "feed_edges" in _CACHE:
        return _CACHE["feed_edges"]
    try:
        rows = _db.eq_q("SELECT source_id, target_id FROM equipment.feeder WHERE kind = 'feed' ORDER BY id")
    except Exception as e:  # noqa: BLE001 — fail-open by contract
        sys.stderr.write("[equipment.bridge] feeder read failed (%s); returning [] (not cached)\n" % type(e).__name__)
        return []
    edges = [(_int(r[0]), _int(r[1])) for r in rows]
    edges = [(s, t) for s, t in edges if s is not None and t is not None]
    _CACHE["feed_edges"] = edges
    return edges


def feeds_fed_by(table_name):
    """(fed_by_names, feeds_names) from equipment.feeder kind='feed', anchored on identity_node(table) — source FEEDS
    target (verified: tx-01 -> pcc-1a -> ups-01). ([], []) when the identity gate fails (an AHU bay meter can NEVER
    claim PCC-2A's fan-out), on miss, or on error. Never raises."""
    try:
        node = identity_node(table_name)
        if not node:
            return [], []
        nid = node["node_id"]
        nodes = _nodes()
        fed_by = [nodes[s]["name"] for s, t in _feed_edges() if t == nid and s in nodes and nodes[s].get("name")]
        feeds = [nodes[t]["name"] for s, t in _feed_edges() if s == nid and t in nodes and nodes[t].get("name")]
        return fed_by, feeds
    except Exception:
        return [], []


# ── small casts (csv rows are all-text) ─────────────────────────────────────────────────────────────────────────────
def _int(v):
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return None


def _bool(v):
    return str(v).strip().lower() in ("t", "true", "1")


def clear_cache():
    """Tests + operational reload (mirrors data/equipment/db.clear_cache)."""
    _CACHE.clear()
