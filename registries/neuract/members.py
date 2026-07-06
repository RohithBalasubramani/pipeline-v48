"""registries/neuract/members.py — a panel's MEMBER meters (THE aggregation source the panel-aggregate stage calls).

Single concern: given a panel reference (an MFM id or name — panel_id varchar is EMPTY in neuract, so a panel IS a meter
row), resolve the member meters that make up that panel's aggregate, from the lt_mfm edge tables.

GROUND-TRUTH EDGE SEMANTICS (introspected + verified — incoming/outgoing are exact mirrors, 0 unmatched each way):
    lt_mfm_outgoing(from_mfm_id, to_mfm_id):  from = the panel/parent,  to = its DOWNSTREAM feeder/member.
    lt_mfm_incoming(from_mfm_id, to_mfm_id):  from = the feeder,        to = the panel/parent  (mirror of outgoing).
So a panel P's MEMBERS (what its aggregate sums) = the `to_mfm_id` rows where from_mfm_id = P in lt_mfm_outgoing.
(coupler / spare / power_quality share the same (from,to) shape — they carry the tie/spare/PQ-tap members; all three are
currently EMPTY but are read so the accessor stays correct the moment rows land.)

Each returned member is {mfm_id, name, neuract_table, role} where role ∈ {outgoing, incoming, coupler, spare,
power_quality} names WHICH edge table it came from (its structural relationship to the panel), and neuract_table is the
gic_* time-series table that member logs to (via meters.table_for) — i.e. exactly what the aggregation then reads.

Honest-degrade: an unknown panel / a panel with no edges → [] (never a fabricated member). [atomic; DB-driven]
"""
from __future__ import annotations

from registries.neuract import _db
from registries.neuract import meters as _meters

# the edge tables that carry membership, in resolution order. All share (from_mfm_id, to_mfm_id).
#   outgoing = downstream members of the panel (the primary aggregation set)
#   coupler / spare / power_quality = tie / spare / PQ-tap members hung off the same panel (from=panel)
_MEMBER_EDGES = ("outgoing", "coupler", "spare", "power_quality")


def _panel_id(panel_ref):
    """Resolve a panel reference (id or name) to its lt_mfm id, or None (honest-degrade for unknown panels)."""
    row = _meters.meter_by(panel_ref)
    if not row:
        return None
    try:
        return int(row["id"])
    except (KeyError, TypeError, ValueError):
        return None


def _member_row(mfm_id, role):
    """Shape one member: {mfm_id, name, neuract_table, role} from the meter registry (honest-degrade on a stale id)."""
    m = _meters.meter_by(mfm_id)
    return {
        "mfm_id": int(mfm_id),
        "name": (m.get("name") if m else None),
        "neuract_table": _meters.table_for(m) if m else None,
        "role": role,
    }


def _edge_targets(edge, panel_id):
    """The `to_mfm_id`s where from_mfm_id = panel_id in the given edge table (the panel's members via that edge)."""
    tbl = f"lt_mfm_{edge}"
    if not _db.table_exists(tbl):
        return []
    got = _db.rows(
        f"SELECT to_mfm_id FROM {tbl} WHERE from_mfm_id = %s ORDER BY to_mfm_id",
        (panel_id,),
    )
    return [r[0] for r in got if r and r[0] is not None]


def members_of(panel_ref):
    """The member meters that make up a panel's aggregate → [{mfm_id, name, neuract_table, role}]. [] if none / unknown.

    THIS is what the panel-aggregate stage calls: it fans the panel out to its constituent gic_* tables (neuract_table)
    to sum. `panel_ref` is an MFM id or name. Members are de-duplicated across edge tables (first edge wins the role),
    preserving the outgoing set first. Honest-degrade: unknown panel or no edges → [] (never fabricated)."""
    pid = _panel_id(panel_ref)
    if pid is None:
        return []
    out, seen = [], set()
    for edge in _MEMBER_EDGES:
        for mid in _edge_targets(edge, pid):
            if mid in seen:
                continue
            seen.add(mid)
            out.append(_member_row(mid, edge))
    return out


def incomers_of(panel_ref):
    """The panel's INCOMING (upstream-source) meters → [{mfm_id, name, neuract_table, role='incoming'}]. [] if none.

    From lt_mfm_outgoing where to_mfm_id = panel: the meters whose DOWNSTREAM set contains this panel — i.e. the meters
    that FEED it (its supply side). VERIFIED on PCC-Panel-1 (317): outgoing rows (17→317),(19→317),(164→317),(166→317)
    = Solar Incomer-1/2 + Transformer-01/02 — the real supply. The old query (lt_mfm_incoming WHERE to_mfm_id=panel)
    returned the MIRROR of the panel's own downstream feeders (incoming is the exact (from,to)-swapped mirror of
    outgoing), so 'incomers' silently duplicated the outgoers and the true supply side was never resolved [PCC-1 fix].
    Falls back to the incoming mirror (WHERE from_mfm_id = panel → to_mfm_id) if the outgoing table is absent."""
    pid = _panel_id(panel_ref)
    if pid is None:
        return []
    if _db.table_exists("lt_mfm_outgoing"):
        got = _db.rows(
            "SELECT from_mfm_id FROM lt_mfm_outgoing WHERE to_mfm_id = %s ORDER BY from_mfm_id",
            (pid,),
        )
    elif _db.table_exists("lt_mfm_incoming"):
        got = _db.rows(
            "SELECT to_mfm_id FROM lt_mfm_incoming WHERE from_mfm_id = %s ORDER BY to_mfm_id",
            (pid,),
        )
    else:
        return []
    seen, out = set(), []
    for r in got:
        mid = r[0]
        if mid is None or mid in seen:
            continue
        seen.add(mid)
        out.append(_member_row(mid, "incoming"))
    return out


def outgoers_of(panel_ref):
    """The panel's OUTGOING (downstream) meters → [{mfm_id, name, neuract_table, role='outgoing'}]. [] if none.

    From lt_mfm_outgoing where from_mfm_id = panel: the feeders this panel FEEDS (its distribution side). This is the
    core of members_of; kept as its own accessor for callers that want only the outgoing set."""
    pid = _panel_id(panel_ref)
    if pid is None:
        return []
    return [_member_row(mid, "outgoing") for mid in _edge_targets("outgoing", pid)]


def member_tables(panel_ref):
    """Just the neuract gic_* table_names of a panel's members (skips members with no table) → [str]. [] if none.

    A convenience for the aggregation: the list of live tables to read + sum, with the null-table members dropped."""
    return [m["neuract_table"] for m in members_of(panel_ref) if m.get("neuract_table")]
