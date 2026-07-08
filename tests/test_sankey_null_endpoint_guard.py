"""SANKEY RENDER-SAFETY GUARD — never ship a null-endpoint link (2026-07-07 pg02 card-13 d3-sankey 'missing: —' crash).

d3-sankey's computeNodeLinks() find() throws 'missing: <id>' on any link whose source/target does not resolve to a
node, crashing the WHOLE card. The roster builder writes RESOLVABLE endpoints, but a later post-fill class killer blanks
a link's source/target string when it byte-matches the default's structural stage id (a sankey endpoint IS topology
identity — it collides with the narrative `source` key the seed-leak class polices). The guard is two-part: the builder
STASHES the resolvable endpoints under a reserved `_endpoints` key (the seed-leak pass skips leading-underscore keys), and
the serve sweep RESTORES a blanked endpoint from that stash, then DROPS any link still unresolved and removes the stash —
so d3-sankey only ever sees resolvable endpoints AND the real member flows survive. Pure unit (no DB, no LLM, no host)."""
from __future__ import annotations

from ems_exec.executor import roster_modes_sankey as SK
from ems_exec.serve import run as SR


def _sankey():
    """A 2-stage sankey shaped like card 13: 1 incomer → pcc-panel → distribution-allocation → 2 meters, one meter dark."""
    return {
        "nodes": [
            {"id": "incomer-a", "label": "A", "value": None},
            {"id": "pcc-panel", "label": "", "value": 1000.0},
            {"id": "distribution-allocation", "label": "", "value": 1000.0},
            {"id": "meter-ups-01", "label": "UPS-01", "value": 600.0},
            {"id": "meter-ups-02", "label": "UPS-02", "value": None},
        ],
        "links": [
            {"source": "incomer-a", "target": "pcc-panel", "value": None},
            {"source": "pcc-panel", "target": "distribution-allocation", "value": 1000.0},
            {"source": "distribution-allocation", "target": "meter-ups-01", "value": 600.0},
            {"source": "distribution-allocation", "target": "meter-ups-02", "value": None},
        ],
    }


def _null_endpoints(sk):
    return sum(1 for l in sk["links"] if l.get("source") in (None, "—", "") or l.get("target") in (None, "—", ""))


def _unresolved(sk):
    ids = {n.get("id") for n in sk.get("nodes") or []}
    return sum(1 for l in sk["links"] if l.get("source") not in ids or l.get("target") not in ids)


def test_stash_records_resolvable_endpoints():
    sk = _sankey()
    SK._stash_endpoints(sk)
    stash = sk[SK._STASH_KEY]
    assert len(stash) == len(sk["links"])
    assert stash[0] == {"source": "incomer-a", "target": "pcc-panel"}
    assert stash[2] == {"source": "distribution-allocation", "target": "meter-ups-01"}


def test_prune_drops_a_genuinely_unresolvable_link():
    # no stash → a link to a node that does not exist (and one with a '—' endpoint) is DROPPED, real edges survive
    sk = _sankey()
    sk["links"].append({"source": "distribution-allocation", "target": "ghost-node", "value": 5.0})
    sk["links"].append({"source": "—", "target": "meter-ups-01", "value": 7.0})
    SK._prune_dark_edges(sk)
    assert _null_endpoints(sk) == 0
    assert _unresolved(sk) == 0
    assert len(sk["links"]) == 4                          # the two bogus links dropped; the 4 real edges kept
    # the real member flow edges are still present with their values
    vals = {(l["source"], l["target"]): l.get("value") for l in sk["links"]}
    assert vals[("distribution-allocation", "meter-ups-01")] == 600.0
    assert vals[("pcc-panel", "distribution-allocation")] == 1000.0


def test_restore_recovers_endpoints_a_later_pass_blanked():
    # simulate the fab-guard over-reach: build (stash), then a later pass NULLS every source/target (values survive)
    sk = _sankey()
    SK._stash_endpoints(sk)
    for l in sk["links"]:
        l["source"] = None
        l["target"] = None
    assert _null_endpoints(sk) == 4                       # every endpoint blanked
    SK._prune_dark_edges(sk)                              # restore from stash, then drop any still-unresolved
    assert _null_endpoints(sk) == 0                       # every endpoint recovered
    assert _unresolved(sk) == 0
    assert len(sk["links"]) == 4                          # ALL real flows preserved (nothing lost)
    assert SK._STASH_KEY not in sk                        # the stash never ships
    # the real member flow values are intact
    vals = {(l["source"], l["target"]): l.get("value") for l in sk["links"]}
    assert vals[("distribution-allocation", "meter-ups-01")] == 600.0


def test_restore_then_drop_when_a_stashed_node_was_removed():
    # a stashed endpoint whose NODE was legitimately removed cannot be restored → that link is dropped, others survive
    sk = _sankey()
    SK._stash_endpoints(sk)
    for l in sk["links"]:
        l["source"] = None
        l["target"] = None
    sk["nodes"] = [n for n in sk["nodes"] if n["id"] != "meter-ups-02"]   # the dark meter node is gone
    SK._prune_dark_edges(sk)
    assert _null_endpoints(sk) == 0
    assert _unresolved(sk) == 0
    assert all(l["target"] != "meter-ups-02" for l in sk["links"])         # its edge dropped
    assert len(sk["links"]) == 3                                           # the other 3 real edges restored


def test_serve_sweep_walks_nested_sankeys_and_never_ships_null_or_stash():
    # the serve sweep finds a sankey ANYWHERE in the completed payload (generic, no card ids) and cleans it
    sk = _sankey()
    SK._stash_endpoints(sk)
    for l in sk["links"]:
        l["source"] = None
        l["target"] = None
    payload = {"flow": {"vm": {"sankey": sk}}, "unrelated": {"x": 1}}
    SR._sweep_sankeys(payload)
    out = payload["flow"]["vm"]["sankey"]
    assert _null_endpoints(out) == 0
    assert _unresolved(out) == 0
    assert SK._STASH_KEY not in out
    assert len(out["links"]) == 4                        # real flows preserved through the serve boundary


def test_empty_or_missing_sankey_is_a_noop():
    SK._prune_dark_edges({})                             # no links key → no-op, no raise
    SK._prune_dark_edges({"links": None})               # listless → no-op
    SK._prune_dark_edges({"nodes": [], "links": []})    # empty graph → stays empty, never raises
    SR._sweep_sankeys(None)                              # non-dict → no raise
    SR._sweep_sankeys({"a": [1, 2, 3]})                 # no sankey anywhere → no raise
