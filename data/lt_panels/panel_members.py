"""data/lt_panels/panel_members.py — THE single source of truth for panel fan-out (topology member resolution).

Every aggregate card + Sankey resolves its members through THIS one function so coverage / degrade behaviour is uniform.
The topology gotchas this file resolves (see V48_RENDER_GUARANTEE_AUDIT §TOPOLOGY):

  · [TOPO-02] direction — fan-out is the FROM side ONLY: `to_mfm_id WHERE from_mfm_id=self`. NEVER lt_mfm_incoming: the
              seed inverts it (a PCC's `incoming` returns its own downstream loads), so incoming is byte-identical to
              outgoing and any loss/meter-gap math built on it collapses to a fabricated 0. We only ever read outgoing.
  · [TOPO-05] recurse — a parent whose only children are themselves EMPTY aggregates (transformer 164 → PCC-Panel-1
              317, own table pcc_panel_1_feedbacks = 0 rows) drills one level down to the grandchildren leaf meters.
  · [TOPO-04/DS-08/VC-04] coverage — filter leaves through has_data; report reporting_count / expected_count so a
              partial feeder sum is labelled partial, never presented as a complete panel total.
  · [TOPO-06] dedup — a leaf reachable via multiple parents (loads 54/57, HT ties) is attributed ONCE (dedup on
              to_mfm_id) so a cross-parent rollup can't double-count.
  · [TOPO-01/07] orphan — a scoped asset with zero outgoing edges (303 of 320) yields members=[] + orphaned=True so
              the caller honest-degrades ('no topology mapped') instead of closing the socket / crashing.

NO hardcoded table names (config.databases.TOPOLOGY_OUTGOING / DATA_SCHEMA) and NO hardcoded thresholds
(config.quality_policy). Pure deterministic PRE — no AI. [worker member resolution]
"""
from config.databases import DATA_DB, DATA_SCHEMA, TOPOLOGY_OUTGOING
from data.db_client import q
from layer1b.resolve.has_data import tables_with_data, tables_with_values

_MAX_DEPTH = 6                                  # topology is <= 5 deep; depth guard against a cycle in the seeded edges
_MEMBERS_CACHE = {}                             # per-process cache keyed (mfm_id, meaningful) — recursion is DB-heavy


def _outgoing(ids):
    """One batched hop DOWN the FROM side: [(to_mfm_id, table_name)] for every child of any id in `ids`. Never touches
    lt_mfm_incoming (inverted by the seed — see TOPO-02). fail-open to [] so a bad edge can't crash the whole resolve."""
    if not ids:
        return []
    id_list = ",".join(str(int(i)) for i in ids)
    try:
        rows = q(DATA_DB,
                 f'SELECT o.to_mfm_id, m.table_name '
                 f'FROM {DATA_SCHEMA}."{TOPOLOGY_OUTGOING}" o '
                 f'JOIN {DATA_SCHEMA}.lt_mfm m ON m.id = o.to_mfm_id '
                 f'WHERE o.from_mfm_id IN ({id_list}) ORDER BY o.id')
    except Exception as e:  # fail-open — a topology read failure honest-degrades to "no members", never a crash
        import sys
        sys.stderr.write(f"[panel_members] outgoing read failed ({str(e)[:80]}) — treating as no children\n")
        return []
    out = []
    for r in rows:
        if r and r[0]:
            out.append((int(r[0]), (r[1] or None)))
    return out


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
    apart from a pure LEAF (terminal). fail-open to empty so a topology read failure just stops recursion."""
    if "_parents" in _MEMBERS_CACHE:
        return _MEMBERS_CACHE["_parents"]
    try:
        ids = {int(r[0]) for r in q(DATA_DB,
               f'SELECT DISTINCT from_mfm_id FROM {DATA_SCHEMA}."{TOPOLOGY_OUTGOING}"') if r and r[0]}
    except Exception:
        ids = set()
    _MEMBERS_CACHE["_parents"] = ids
    return ids
