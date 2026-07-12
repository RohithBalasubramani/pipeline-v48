"""data/equipment/edges.py — BAY-ANCHORED panel rosters from the equipment schema, behind a default-OFF kill-switch
and a per-panel human-vetted allowlist, protected by a TWO-SIDED GUARD.

Rosters are resolved the way CMD_V2 itself does (MFM.objects.filter(reference_id=...)): the allowlist maps a canonical
panel table_name -> {"nodes": [equipment.equipment.key, ...], "extra_ok": [canonical_table, ...]} and the roster is the
equipment.mfm bays whose reference_id sits on those nodes with role == direction (spare NEVER rostered — every
mfm_pefc_* ds1 mock sits there; coupler never). equipment.feeder is NOT a roster source (fatal-1 rework: its
equipment_id fan-out double-counted multi-meter nodes and fabricated rosters for hosting-panel mis-pointers).

TWO-SIDED GUARD (per direction, against the registry mirror):
  (i)  never LOSE a mirror member — resolved must be a SUPERSET of the mirror set;
  (ii) never GAIN unvetted — extras (resolved minus mirror) must all be named in the entry's extra_ok tables;
  (iii) all-or-nothing — ANY role-selected bay that fails to bridge (table not uniquely in the registry) -> None,
        so a partial roster can never sum a subset as a panel total.
Violation -> None + one ASCII stderr line; the caller falls back to today's mirror source byte-identically.

Registry reads go DIRECTLY through data/db_client.q against the cmd_catalog registry_* mirror (NOT via
data.registry.lt_mfm — that module consults THIS one; a module-level import would cycle). Registry-side table
uniqueness (320/320) is checked, so a dup-TWIN bay (selected by reference_id) still bridges unambiguously.

enabled()/the allowlist are LATCHED at first call so lt_mfm._CACHE / panel_members._MEMBERS_CACHE / the
panel_members_block lru_cache never see a mid-run source switch (restart or clear_cache() to re-read). Deterministic
outcomes are cached per (panel_table, direction); DB-error outcomes are NEVER cached (retry next call).  [stream A]
"""
from obs.errfmt import record_exc as _record_exc   # failures-channel telemetry [EH F4]
import sys

from config.databases import CMD_CATALOG
from data.db_client import q as _q
from data.equipment import db as _db

_STATE = {}     # latched knobs: enabled / allowlist
_CACHE = {}     # successful registry/node reads (failures never cached)
_ROSTERS = {}   # (panel_table, direction) -> list[int]|None — deterministic outcomes only


# ── knobs (latched) ─────────────────────────────────────────────────────────────────────────────────────────────────
def enabled():
    """cfg('equipment.topology.enabled','off') LATCHED at first call (kill-switch; default off => feature inert)."""
    if "enabled" not in _STATE:
        try:
            from config.app_config import flag_on
            _STATE["enabled"] = flag_on("equipment.topology.enabled")   # D6: unified vocabulary — 't' now counts (drift repair)
        except Exception:
            _STATE["enabled"] = False
    return _STATE["enabled"]


def _allowlist():
    """The per-panel allowlist (json cfg 'equipment.topology.panel_allowlist', default {}), LATCHED with the switch.
    {} => the feature is inert even when enabled — each entry is a staged, human-verified DB row."""
    if "allowlist" not in _STATE:
        try:
            from config.app_config import cfg
            al = cfg("equipment.topology.panel_allowlist", {})
            _STATE["allowlist"] = al if isinstance(al, dict) else {}
        except Exception:
            _STATE["allowlist"] = {}
    return _STATE["allowlist"]


# ── registry mirror reads (direct; cycle-free) ──────────────────────────────────────────────────────────────────────
def _registry_by_table():
    """{table_name: canonical_id} over registry_lt_mfm, UNIQUE tables only (a registry-side dup — none today at
    320/320 — is un-bridgeable and simply misses). {} for THIS call on DB error (not cached)."""
    if "reg_by_table" in _CACHE:
        return _CACHE["reg_by_table"]
    try:
        rows = _q(CMD_CATALOG, "SELECT id, table_name FROM registry_lt_mfm WHERE table_name IS NOT NULL")
    except Exception as e:  # noqa: BLE001 — fail-open by contract
        sys.stderr.write("[equipment.edges] registry read failed (%s); returning {} (not cached)\n" % type(e).__name__)
        _record_exc("equipment.edges.registry", e)   # + the failures channel (stderr never reached the runbooks) [EH F4]
        return {}
    seen, dups = {}, set()
    for r in rows:
        cid, tbl = _int(r[0]), (r[1] or "").strip()
        if cid is None or not tbl:
            continue
        if tbl in seen:
            dups.add(tbl)
        seen[tbl] = cid
    for tbl in dups:
        seen.pop(tbl, None)
    _CACHE["reg_by_table"] = seen
    return seen


def _mirror_edges():
    """[(edge_id, from_mfm_id, to_mfm_id)] over the WHOLE registry_lt_mfm_outgoing mirror (93 rows), edge-id order.
    None for THIS call on DB error (not cached) — callers must fall back, never treat an outage as an empty mirror."""
    if "mirror_edges" in _CACHE:
        return _CACHE["mirror_edges"]
    try:
        rows = _q(CMD_CATALOG, "SELECT id, from_mfm_id, to_mfm_id FROM registry_lt_mfm_outgoing ORDER BY id")
    except Exception as e:  # noqa: BLE001 — fail-open by contract
        sys.stderr.write("[equipment.edges] mirror read failed (%s); returning None (not cached)\n" % type(e).__name__)
        _record_exc("equipment.edges.mirror", e)
        return None
    edges = [(_int(r[0]), _int(r[1]), _int(r[2])) for r in rows]
    edges = [(e, f, t) for e, f, t in edges if f is not None and t is not None]
    _CACHE["mirror_edges"] = edges
    return edges


def _mirror_members(panel_cid, direction):
    """The mirror member ids for the SAME direction the roster is being built for (deduped, mirror order):
      outgoing = to_mfm_id WHERE from_mfm_id=panel (edge order — outgoing_edges' semantics);
      incoming = the TRANSPOSE: from_mfm_id WHERE to_mfm_id=panel, ascending (exactly incomers_of's semantics).
    None on mirror read error (guard must not pass against an unknowable mirror)."""
    edges = _mirror_edges()
    if edges is None:
        return None
    if direction == "outgoing":
        got = [t for _e, f, t in edges if f == panel_cid]
    else:
        got = sorted({f for _e, f, t in edges if t == panel_cid})
    return list(dict.fromkeys(got))


def _nodes_by_key():
    """{equipment.equipment.key: id} for allowlist node resolution. {} for THIS call on DB error (not cached)."""
    if "nodes_by_key" in _CACHE:
        return _CACHE["nodes_by_key"]
    try:
        rows = _db.eq_q("SELECT key, id FROM equipment.equipment WHERE key IS NOT NULL")
    except Exception as e:  # noqa: BLE001 — fail-open by contract
        sys.stderr.write("[equipment.edges] node-key read failed (%s); returning {} (not cached)\n" % type(e).__name__)
        _record_exc("equipment.edges.node_key", e)
        return {}
    got = {}
    for r in rows:
        key, nid = (r[0] or "").strip(), _int(r[1])
        if key and nid is not None:
            got[key] = nid
    _CACHE["nodes_by_key"] = got
    return got


# ── the roster door ─────────────────────────────────────────────────────────────────────────────────────────────────
def panel_roster(panel_table, direction):
    """Canonical lt_mfm member ids for an ALLOWLISTED panel via bay-anchored resolution, in mirror order first then
    vetted extras by canonical id ascending. None = knob off / panel not allowlisted / guard failed / DB error ->
    the caller falls back to today's source byte-identically. Never raises."""
    try:
        if direction not in ("incoming", "outgoing") or not panel_table:
            return None
        if not enabled():
            return None
        key = (panel_table, direction)
        if key in _ROSTERS:
            return _ROSTERS[key]
        roster, cacheable = _resolve(panel_table, direction)
        if cacheable:
            _ROSTERS[key] = roster
        return roster
    except Exception:
        return None


def _fail(panel_table, direction, why):
    """One ASCII guard-violation line -> None (the honest mirror fallback)."""
    line = "[equipment.edges] roster guard failed for %s/%s: %s\n" % (str(panel_table), direction, why)
    sys.stderr.write(line.encode("ascii", "replace").decode())
    return None


def _resolve(panel_table, direction):
    """(roster_or_None, cacheable). Deterministic outcomes (roster / not-allowlisted / guard violation) are cacheable;
    DB-error outcomes are not (failures never cached — a :5432 blip must not disable the feature until restart)."""
    entry = _allowlist().get(panel_table)
    if not isinstance(entry, dict):
        return None, True                                             # not allowlisted -> today's source

    keys = [str(k).strip() for k in (entry.get("nodes") or []) if str(k or "").strip()]
    if not keys:
        return _fail(panel_table, direction, "allowlist entry has no nodes"), True
    nodes_by_key = _nodes_by_key()
    if not nodes_by_key:
        return None, False                                            # DB error (already logged) -> retry next call
    node_ids = set()
    for k in keys:
        nid = nodes_by_key.get(k)
        if nid is None:
            return _fail(panel_table, direction, "unknown node key in allowlist entry"), True
        node_ids.add(nid)

    # bay members: equipment.mfm WHERE reference_id IN nodes AND role == direction (spare/coupler NEVER rostered)
    by_table = _db.mfm_by_table()
    if not by_table:
        return None, False                                            # DB error -> retry next call
    bays = []
    for rows in by_table.values():
        for r in rows:
            if (r.get("role") or "").strip() == direction and _int(r.get("reference_id")) in node_ids:
                bays.append(r)
    bays.sort(key=lambda r: _int(r.get("id")) or 0)

    # bridge each bay table -> canonical id (all-or-nothing: one unbridgeable member -> no partial roster EVER)
    reg = _registry_by_table()
    if not reg:
        return None, False                                            # DB error -> retry next call
    resolved = []
    for r in bays:
        cid = reg.get((r.get("table_name") or "").strip())
        if cid is None:
            return _fail(panel_table, direction, "unbridgeable member table (all-or-nothing)"), True
        if cid not in resolved:
            resolved.append(cid)

    panel_cid = reg.get(panel_table)
    if panel_cid is None:
        return _fail(panel_table, direction, "panel table not in the registry"), True
    mirror = _mirror_members(panel_cid, direction)
    if mirror is None:
        return None, False                                            # mirror unknowable -> retry next call

    # TWO-SIDED GUARD (i): never LOSE a mirror member
    rset = set(resolved)
    if any(m not in rset for m in mirror):
        return _fail(panel_table, direction, "would lose mirror members"), True
    # TWO-SIDED GUARD (ii): never GAIN a member not explicitly vetted in extra_ok
    extras = sorted(rset - set(mirror))
    if extras:
        vetted = {reg.get(str(t).strip()) for t in (entry.get("extra_ok") or [])}
        vetted.discard(None)
        if not set(extras) <= vetted:
            return _fail(panel_table, direction, "unvetted extra members beyond the mirror"), True

    return list(mirror) + extras, True                                # mirror order first, extras ascending


def equipment_parents():
    """Canonical ids of allowlisted panels whose OUTGOING roster is non-None — the ONLY ids that may green
    has_feeders (an empty-mirror meter can never gain parenthood implicitly). set() when off / on any error."""
    try:
        if not enabled():
            return set()
        out = set()
        for tbl in _allowlist():
            if panel_roster(tbl, "outgoing") is None:
                continue
            cid = _registry_by_table().get(tbl)
            if cid is not None:
                out.add(cid)
        return out
    except Exception:
        return set()


def _int(v):
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return None


def clear_cache():
    """Tests + operational reload: drops the latched knobs, the read caches and the roster cache."""
    _STATE.clear()
    _CACHE.clear()
    _ROSTERS.clear()
