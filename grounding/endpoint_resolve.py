"""grounding/endpoint_resolve.py — resolve a card's WS endpoint + expected frame SHAPE, pre-validate it against the
LIVE endpoint set, and (for a PCC panel-aggregate history card whose own table is empty) fan the history out over the
panel's real feeders. ZERO AI — this NAMES an endpoint/shape/feeder-set; it never fetches a frame or emits a number.

THE PROBLEMS this covers:
  · [ER-1] the SAME endpoint (energy-power) emits `queue` for a feeder but `widgets` for a PCC panel — the card's fill
    mapper expects ONE shape. We attach the policy `expected_shape` (queue|buckets|widgets) so POST can DETECT a
    server-side shape fork (`frame_shape_mismatch`) instead of silently swapping to the page frame.
  · [ER-2] a PCC panel's history endpoint queries the panel's OWN `pcc_panel_N_feedbacks` table (0 rows, breaker-only)
    → `buckets(n=0)` ok=True (silent blank). We detect an empty-own-table PCC aggregate + fan the history out over the
    panel's populated outgoing feeders (`history_fanout`) so POST aggregates real feeder history instead.
  · [ER-4] `demand-profile` (and any history endpoint) has NO `pcc_panel` strategy → falls back to the feeder strategy
    on the empty feedbacks table. Same fan-out fix; if no populated feeder exists, honest-degrade with a reason.
  · [ER-5] `ht_panel`/`sub_panel` are dead categories — an unconfigured (page,scope) yields NO policy row → we return
    an honest `endpoint=None` + reason, never guess a dead strategy.
  · [ER-7] only 5 domains have a history variant. `is_history` from the policy tells the card whether a date control is
    even meaningful; a history-less domain returns `is_history=False` so POST can disable the date control (no no-op).
  · [ER-8] a RETIRED / invented endpoint must NOT open a WS (cold-connect timeout ceiling). We pre-validate the resolved
    endpoint against `endpoint_registry.LIVE_ENDPOINTS` and short-circuit `ws_ok=False` + reason WITHOUT a WS.

Every policy (page→endpoint→shape→is_history, scope normalization) is an EDITABLE ROW read through `config.*` accessors.
The live-endpoint truth is DERIVED from ems_backend's own route table (endpoint_registry). No hardcoded endpoint map.
"""
from __future__ import annotations

from config import endpoint_policy as ep_cfg
from config import quality_policy as qp
from config import reason_templates as rt
from config.databases import DATA_DB, DATA_SCHEMA
from data.db_client import q
from layer1b.resolve import has_data
from layer2.emit.data.endpoint_registry import LIVE_ENDPOINTS, is_live

# ── page-key → ems page CODE ──────────────────────────────────────────────────────────────────────
# The catalog page_key is `<shell>/<tail>` (e.g. 'individual-feeder-meter-shell/energy-power') but `endpoint_policy`
# is keyed by the bare ems page code ('energy-power'). Two FE tails differ from their ems code by a naming convention
# only. Kept as an editable text policy in data_quality_policy (key 'page_tail_alias.<tail>' → ems code); a missing
# alias means the tail already equals its ems code. NO hardcoded alias map in logic.
def _ems_page_code(page_key):
    tail = (page_key or "").rsplit("/", 1)[-1]
    alias = qp.txt(f"page_tail_alias.{tail}")
    return alias or tail


# ── resolver_scope (meter|asset|site|panel|none) → endpoint_policy scope (single_asset|panel_aggregate) ────────────
# The card_handling.resolver_scope vocabulary is finer than endpoint_policy's. The mapping is a POLICY, so it is an
# editable row set in data_quality_policy (key 'scope_map.<resolver_scope>' → 'single_asset'|'panel_aggregate').
# A sensible default is applied only when the policy row is absent (panel → aggregate, everything else → single_asset),
# and that default is itself overridable via 'scope_map.default'.
def _policy_scope(resolver_scope):
    rs = (resolver_scope or "").strip().lower()
    mapped = qp.txt(f"scope_map.{rs}")
    if mapped:
        return mapped
    default = qp.txt("scope_map.default", "single_asset")
    if rs in ("panel", "site"):
        return qp.txt("scope_map.panel_default", "panel_aggregate")
    return default


def _esc(s):
    return str(s).replace("'", "''")


def _panel_own_table_empty(panel_table):
    """True iff the panel's OWN data table has zero data-bearing rows (the pcc_panel_N_feedbacks 0-row / breaker-only
    case). Uses the shared has_data probe so 'empty' means the same thing everywhere. A missing table is treated as
    empty (→ fan out)."""
    if not panel_table:
        return True
    return panel_table not in has_data.tables_with_data([panel_table])


def _panel_feeders(panel_mfm_id):
    """The panel's outgoing feeders as [{mfm_id, table_name, name}] — the FROM-side fan-out (never the inverted
    incoming set). Read from lt_mfm_outgoing ⋈ lt_mfm on the DATA db. [ER-2/4 history fan-out source]"""
    if panel_mfm_id in (None, ""):
        return []
    rows = q(DATA_DB,
             "SELECT o.to_mfm_id, m.table_name, m.name "
             f"FROM {DATA_SCHEMA}.lt_mfm_outgoing o "
             f"JOIN {DATA_SCHEMA}.lt_mfm m ON m.id = o.to_mfm_id "
             f"WHERE o.from_mfm_id = {int(panel_mfm_id)} "
             "ORDER BY o.to_mfm_id")
    out = []
    for r in rows:
        if not r or not r[1]:
            continue
        out.append({"mfm_id": int(r[0]) if r[0] not in (None, "") else None,
                    "table_name": r[1], "name": (r[2] or "").strip()})
    return out


def _history_fanout(panel_mfm_id):
    """For an empty-own-table PCC-panel HISTORY card: the panel's POPULATED feeders (has_data-filtered, de-duplicated)
    that carry real power history, so POST can aggregate feeder history instead of the empty feedbacks table.

    Returns {members:[{mfm_id,table_name,name}], expected, reporting, reason}. When zero feeders report, `members` is []
    and a reason is set so the card honest-degrades ('panel has no metered feeders')."""
    feeders = _panel_feeders(panel_mfm_id)
    expected = len(feeders)
    tables = [f["table_name"] for f in feeders]
    populated = has_data.tables_with_data(tables) if tables else set()
    # de-dup on table_name (shared children reachable via >1 parent are attributed once) [TOPO-06 discipline]
    seen, members = set(), []
    for f in feeders:
        t = f["table_name"]
        if t in populated and t not in seen:
            seen.add(t)
            members.append(f)
    reporting = len(members)
    reason = None
    if expected == 0:
        reason = rt.reason("no_topology", asset=str(panel_mfm_id))
    elif reporting == 0:
        reason = rt.reason("no_metered_feeders", asset=str(panel_mfm_id))
    return {"members": members, "expected": expected, "reporting": reporting, "reason": reason}


def resolve(page_key, resolver_scope, *, panel_mfm_id=None, panel_table=None):
    """Resolve a card's endpoint fact-sheet from config + a live pre-flight. NAMES only — no frame is fetched.

    `page_key`      — the catalog page_key ('<shell>/<tail>').
    `resolver_scope`— card_handling.resolver_scope (meter|asset|site|panel|none).
    `panel_mfm_id`  — the resolved panel's mfm_id (only used for a panel_aggregate history fan-out).
    `panel_table`   — the panel's OWN neuract table_name (to detect the empty-feedbacks case).

    Returns a fact-sheet dict:
        {
          ems_page_code, policy_scope,          # the normalized keys used for the policy lookup
          endpoint,                             # the resolved WS endpoint (None if unconfigured)
          expected_shape,                       # queue | buckets | widgets — the shape the card's fill mapper reads
          is_history,                           # date-navigable? (drives whether a date control is meaningful) [ER-7]
          date_control: enabled | disabled,     # convenience flag = is_history AND endpoint live
          ws_ok,                                # False → do NOT open a WS (unconfigured/retired) [ER-8]
          endpoint_live,                        # endpoint ∈ ems_backend LIVE_ENDPOINTS
          history_fanout,                        # {members,expected,reporting,reason} for an empty PCC-panel history, else None
          reason,                                # honest machine→human reason when ws_ok=False / degraded, else None
        }
    """
    ems_code = _ems_page_code(page_key)
    scope = _policy_scope(resolver_scope)

    out = {
        "ems_page_code": ems_code, "policy_scope": scope,
        "endpoint": None, "expected_shape": None, "is_history": False,
        "date_control": "disabled", "ws_ok": False, "endpoint_live": False,
        "history_fanout": None, "reason": None,
    }

    pol = ep_cfg.policy(ems_code, scope)
    if not pol or not pol.get("endpoint"):
        # [ER-5] unconfigured (page,scope) — never guess a dead strategy; honest-degrade with a reason.
        out["reason"] = rt.reason("endpoint_unconfigured", page=ems_code, scope=scope)
        return out

    endpoint = pol["endpoint"]
    live = is_live(endpoint)
    out.update(endpoint=endpoint, expected_shape=pol.get("expected_shape"),
               is_history=bool(pol.get("is_history")), endpoint_live=live)

    if not live:
        # [ER-8] retired / invented endpoint — short-circuit, do NOT open a WS (avoid the cold-connect timeout ceiling).
        out["reason"] = rt.reason("endpoint_retired", endpoint=endpoint,
                                  live=", ".join(sorted(LIVE_ENDPOINTS)))
        return out

    out["ws_ok"] = True
    out["date_control"] = "enabled" if out["is_history"] else "disabled"

    # [ER-2/4] PCC panel-aggregate HISTORY whose own table is empty → the history strategy would read the empty
    # feedbacks table (buckets n=0, silent). Pre-resolve the feeder fan-out so POST aggregates real feeder history.
    if scope == "panel_aggregate" and out["is_history"] and _panel_own_table_empty(panel_table):
        fan = _history_fanout(panel_mfm_id)
        out["history_fanout"] = fan
        if fan["reporting"] == 0:
            # no populated feeder to aggregate → the card honest-degrades; still ws_ok=False so POST opens no WS.
            out["ws_ok"] = False
            out["reason"] = fan["reason"] or rt.reason("no_metered_feeders", asset=str(panel_mfm_id))

    return out


def endpoint(page_key, resolver_scope):
    """Convenience: just the resolved endpoint NAME (or None) for a (page, scope)."""
    return resolve(page_key, resolver_scope)["endpoint"]


def expected_shape(page_key, resolver_scope):
    """Convenience: just the expected frame shape (queue|buckets|widgets) or None."""
    return resolve(page_key, resolver_scope)["expected_shape"]
