"""data/lt_panels/panel_members.py — THE single source of truth for panel fan-out (topology member resolution).

Every aggregate card + Sankey resolves its members through THIS one function so coverage / degrade behaviour is uniform.
Edges are read from the CANONICAL registry (data/registry/lt_mfm.py — cmd_catalog `registry_*` mirror-first, live
neuract fallback), keyed by canonical lt_mfm.id — the SAME id-space asset_candidates now emits, so a pipeline mfm_id
can never resolve a FOREIGN asset's subtree again (the AUDIT-3 collision). Gotchas resolved here:

  · [TOPO-02] direction — fan-out is the FROM side ONLY (`to_mfm_id WHERE from_mfm_id=self`). Canonical lt_mfm_incoming
              is the verified EXACT mirror of lt_mfm_outgoing (from=receiver, to=source; 0 unmirrored rows both ways) —
              well-formed and legitimately usable for UPSTREAM/SLD source rendering, but fan-out stays on outgoing so
              parent/child can never be misread. (The old lt_feeder root-fix seam is DELETED: its premise — an inverted
              dummy self-M2M seed — was disproven by AUDIT-3, lt_feeder is empty canonical-wide, and the probe was a
              needless request-time tunnel read. If lt_feeder is ever seeded, add it to data/registry/lt_mfm.py.)
  · [TOPO-05] recurse — a parent whose only children are themselves EMPTY aggregates (transformer 164 → PCC-Panel-1
              317, own table pcc_panel_1_feedbacks = 0 rows) drills one level down to the grandchildren leaf meters.
  · [TOPO-04/DS-08/VC-04] coverage — filter leaves through has_data; report reporting_count / expected_count so a
              partial feeder sum is labelled partial, never presented as a complete panel total.
  · [TOPO-06] dedup — a leaf reachable via multiple parents (loads 54/57, HT ties) is attributed ONCE (dedup on
              to_mfm_id) so a cross-parent rollup can't double-count.
  · [TOPO-01/07] orphan — a scoped asset with zero outgoing edges yields members=[] + orphaned=True so the caller
              honest-degrades ('no topology mapped') instead of closing the socket / crashing.

NO hardcoded table names (data/registry mirror routing) and NO hardcoded thresholds (config.quality_policy).
Pure deterministic PRE — no AI. [worker member resolution]
"""
from data.registry.lt_mfm import outgoing_edges as _outgoing, parent_ids as _registry_parents
from layer1b.resolve.has_data import tables_with_data, tables_with_values

_MAX_DEPTH = 6                                  # topology is <= 5 deep; depth guard against a cycle in the seeded edges
_MEMBERS_CACHE = {}                             # per-process cache keyed (mfm_id, meaningful) — recursion is DB-heavy


def panel_members(mfm_id, meaningful=False):
    """The de-duplicated, recursed, has_data-filtered LEAF MEMBERS of an aggregate panel/parent `mfm_id`.

    Walks the FROM side (never incoming); when a child's OWN table is empty AND it is itself a parent (an empty
    aggregate), recurse through it to its grandchildren; a child that is data-bearing (or a data-less pure leaf) is a
    terminal member. Dedup on to_mfm_id so shared descendants are attributed once. `meaningful=True` uses the
    value-aware has_data (>= value_min non-null metric columns) instead of mere row-existence.

    Returns {
      members:        [{mfm_id, table, reporting(bool)}]  — de-duplicated terminal members (reporting + non-reporting)
      reporting_count: int   — members whose table passes the has_data filter (contribute a real number)
      expected_count:  int   — total distinct terminal members (the honest denominator; empties are NOT dropped)
      orphaned:        bool   — True when mfm_id has NO outgoing edge at all (leaf/unmapped → caller degrades)
    }
    """
    root = int(mfm_id)
    ck = (root, bool(meaningful))
    if ck in _MEMBERS_CACHE:
        return _MEMBERS_CACHE[ck]

    parents = _parent_ids()                                    # ids that fan out — an id in here is an aggregate node
    first = _outgoing([root])
    if not first:
        # [TOPO-01/07] scoped asset has no outgoing edge → orphan; caller renders single-asset or "no topology mapped"
        res = {"members": [], "reporting_count": 0, "expected_count": 0, "orphaned": True}
        _MEMBERS_CACHE[ck] = res
        return res

    # ── BFS DOWN the FROM side, recursing through empty-aggregate children to leaf members (TOPO-05) ────────────────
    terminals = {}                                            # to_mfm_id → table  (dict = dedup on device id, TOPO-06)
    visited = {root}
    frontier = first
    depth = 0
    while frontier and depth < _MAX_DEPTH:
        depth += 1
        # which of this level's child tables actually have rows (row-existence gate for the recurse decision)
        level_tables = [t for _, t in frontier if t]
        live_tables = tables_with_data(level_tables) if level_tables else set()
        next_frontier = []
        for cid, tbl in frontier:
            if cid in visited:
                continue
            visited.add(cid)
            is_aggregate = cid in parents
            has_rows = bool(tbl) and tbl in live_tables
            if is_aggregate and not has_rows:
                # empty aggregate (e.g. PCC-Panel-N feedbacks = 0 rows) → drill one level to its grandchildren
                next_frontier.extend(_outgoing([cid]))
            else:
                # a data-bearing node OR a pure leaf (leaf with an empty table is STILL an expected member: honest
                # denominator — we count it, mark it non-reporting, and never silently drop it from expected_count)
                terminals[cid] = tbl                          # dedup: later parents pointing at the same leaf overwrite same key
        frontier = next_frontier

    # ── coverage: which terminals actually carry usable data (meaningful → value-aware; else row-existence) ─────────
    all_tables = [t for t in terminals.values() if t]
    if meaningful:
        reporting_tables = tables_with_values(all_tables) if all_tables else set()
    else:
        reporting_tables = tables_with_data(all_tables) if all_tables else set()

    members = []
    reporting_count = 0
    for cid in sorted(terminals):                             # stable order for deterministic assembly downstream
        tbl = terminals[cid]
        is_reporting = bool(tbl) and tbl in reporting_tables
        if is_reporting:
            reporting_count += 1
        members.append({"mfm_id": cid, "table": tbl, "reporting": is_reporting})

    res = {
        "members": members,
        "reporting_count": reporting_count,
        "expected_count": len(members),
        "orphaned": False,
    }
    _MEMBERS_CACHE[ck] = res
    return res


def _parent_ids():
    """The set of mfm_ids that fan out (have >= 1 outgoing edge) — used to tell an EMPTY AGGREGATE (recurse through it)
    apart from a pure LEAF (terminal). CANONICAL registry parents (mirror-first). fail-open to empty so a topology read
    failure just stops recursion."""
    if "_parents" not in _MEMBERS_CACHE:
        _MEMBERS_CACHE["_parents"] = _registry_parents()
    return _MEMBERS_CACHE["_parents"]
