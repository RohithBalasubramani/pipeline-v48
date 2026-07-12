"""registries/neuract/topology.py — the directed EDGE list for SLD / topology views (from the lt_mfm_* edge tables).

Single concern: hand back the plant's connectivity graph as [{source, target, kind}] where source/target are MFM ids and
kind names the edge table it came from. This is the metadata a single-line-diagram / topology card draws from.

GROUND TRUTH (introspected): lt_mfm_outgoing carries the canonical directed feed edges (from = parent/panel, to =
downstream feeder); lt_mfm_incoming is its exact mirror, so the directed graph is built from OUTGOING alone to avoid
duplicate reversed edges. coupler / spare / power_quality (currently EMPTY) are included as their own `kind`s so ties /
spares / PQ taps show the moment rows land. Optionally decorate each endpoint with its name/table via `named=True`.

Honest-degrade: a missing edge table → skipped; no edges → []. Never fabricates an edge. [atomic; DB-driven; cached]
"""
from __future__ import annotations

from registries.neuract import _db
from registries.neuract import meters as _meters

# directed edges for the graph. OUTGOING = the canonical feed direction (parent→child); incoming is its mirror, so it is
# deliberately excluded here to keep the directed graph free of duplicate reversed edges.
_EDGE_KINDS = ("outgoing", "coupler", "spare", "power_quality")

_CACHE: dict = {}   # bool(named) -> edge list


def _edge_rows(kind):
    tbl = f"lt_mfm_{kind}"
    if not _db.table_exists(tbl):
        return []
    return _db.rows(f"SELECT from_mfm_id, to_mfm_id FROM {tbl} ORDER BY from_mfm_id, to_mfm_id")


def _decorate(mfm_id):
    m = _meters.meter_by(mfm_id)
    return {
        "id": int(mfm_id),
        "name": (m.get("name") if m else None),
        "neuract_table": _meters.table_for(m) if m else None,
    }


def edges(named=False):
    """The directed topology edges → [{source, target, kind}]. [] if none.

    source/target are MFM ids; kind ∈ {outgoing, coupler, spare, power_quality} (the edge table it came from — 'outgoing'
    = the canonical parent→child feed). With named=True each edge is instead {source:{id,name,neuract_table},
    target:{...}, kind} for a card that wants labels without a second lookup. Cached per-process per `named`."""
    ck = bool(named)
    if ck in _CACHE:
        return list(_CACHE[ck])
    out = []
    for kind in _EDGE_KINDS:
        for src, tgt in _edge_rows(kind):
            if src is None or tgt is None:
                continue
            if named:
                out.append({"source": _decorate(src), "target": _decorate(tgt), "kind": kind})
            else:
                out.append({"source": int(src), "target": int(tgt), "kind": kind})
    _CACHE[ck] = out
    return list(out)


def neighbors(mfm_ref, direction="down"):
    """The immediate neighbors of a meter in the feed graph → [mfm_id].

    direction='down' (default) = who this meter FEEDS (outgoing to's); 'up' = who FEEDS this meter (outgoing from's, i.e.
    its parent). [] for an unknown meter or a leaf/root. Honest-degrade, never fabricated."""
    row = _meters.meter_by(mfm_ref)
    if not row:
        return []
    try:
        mid = int(row["id"])
    except (KeyError, TypeError, ValueError):
        return []
    if not _db.table_exists("lt_mfm_outgoing"):
        return []
    if direction == "up":
        got = _db.rows("SELECT from_mfm_id FROM lt_mfm_outgoing WHERE to_mfm_id = %s ORDER BY from_mfm_id", (mid,))
    else:
        got = _db.rows("SELECT to_mfm_id FROM lt_mfm_outgoing WHERE from_mfm_id = %s ORDER BY to_mfm_id", (mid,))
    return [r[0] for r in got if r and r[0] is not None]


