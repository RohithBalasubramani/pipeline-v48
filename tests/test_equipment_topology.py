"""tests/test_equipment_topology.py — stream A: the table_name bridge, the identity gate, the bay-anchored
allowlisted rosters (two-sided guard), the lt_mfm/members merge, and knobs-off byte-identity.

LOCAL-ONLY: every read is cmd_catalog :5432 (equipment schema + registry_* mirror); anything that could touch the
:5433 tunnel (data.neuract_live live meters/_db) is monkeypatched. The whole file passes with the tunnel down."""
import pytest

from config.databases import CMD_CATALOG
from data.db_client import q

# ── verified live fixtures (see outputs/equipment_wiring/stream_a.md) ───────────────────────────────────────────────
PANEL_TABLE = "pcc_panel_1_feedbacks"                     # canonical 317
PANEL_CID = 317
HHF1 = "gic_01_n10_hhf_01_type_01_300a_600kvar_p1"        # canonical 8   (real feeder beyond the mirror)
HHF2 = "gic_02_n10_hhf_02_type_01_300a_600kvar_p1"        # canonical 18
ALLOW_FULL = {PANEL_TABLE: {"nodes": ["pcc-1a", "pcc-1b"], "extra_ok": [HHF1, HHF2]}}
ALLOW_UNVETTED = {PANEL_TABLE: {"nodes": ["pcc-1a", "pcc-1b"], "extra_ok": []}}
ALLOW_HALF = {PANEL_TABLE: {"nodes": ["pcc-1a"], "extra_ok": [HHF1]}}          # loses the gic_02 mirror members


def _local_up():
    try:
        return bool(q(CMD_CATALOG, "SELECT 1 FROM registry_lt_mfm LIMIT 1"))
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _local_up(), reason="cmd_catalog :5432 / registry mirror unavailable")


@pytest.fixture(autouse=True)
def _fresh_caches():
    """Every test starts and ends with the equipment latches/caches and the lt_mfm cache clean (knob latching is
    per-process by design — tests re-latch explicitly via _knobs)."""
    from data.equipment import bridge, db, edges
    from data.registry import lt_mfm
    for m in (bridge, db, edges):
        m.clear_cache()
    lt_mfm._CACHE.clear()
    yield
    for m in (bridge, db, edges):
        m.clear_cache()
    lt_mfm._CACHE.clear()


def _knobs(monkeypatch, enabled="on", allowlist=None):
    """Latch the two stream-A knobs to test values (cfg passthrough for every other key) and hand back edges."""
    from config import app_config as _ac
    real = _ac.cfg

    def fake(key, default):
        if key == "equipment.topology.enabled":
            return enabled
        if key == "equipment.topology.panel_allowlist":
            return allowlist if allowlist is not None else {}
        return real(key, default)

    monkeypatch.setattr(_ac, "cfg", fake)
    from data.equipment import edges
    edges.clear_cache()
    return edges


def _mirror_outgoing(pid):
    rows = q(CMD_CATALOG, f"SELECT to_mfm_id FROM registry_lt_mfm_outgoing WHERE from_mfm_id={int(pid)} ORDER BY id")
    return list(dict.fromkeys(int(r[0]) for r in rows))


def _mirror_incoming(pid):
    rows = q(CMD_CATALOG, f"SELECT from_mfm_id FROM registry_lt_mfm_outgoing WHERE to_mfm_id={int(pid)} "
                          f"ORDER BY from_mfm_id")
    return list(dict.fromkeys(int(r[0]) for r in rows))


def _canon(table):
    rows = q(CMD_CATALOG, f"SELECT id FROM registry_lt_mfm WHERE table_name='{table}'")
    return int(rows[0][0]) if rows else None


# ═══ bridge: id-space proof + dup skip + aliases ════════════════════════════════════════════════════════════════════
def test_bridge_id_space_proof():
    """equipment.mfm id 13 <-> canonical 171 via gic_15_n3_pcc_01_transformer_01_se — table_name is the ONLY bridge."""
    from data.equipment import bridge
    tbl = "gic_15_n3_pcc_01_transformer_01_se"
    row = bridge.eq_row_for_table(tbl)
    assert row is not None and row["eq_mfm_id"] == 13
    assert _canon(tbl) == 171
    assert row["eq_mfm_id"] != _canon(tbl)                # DIFFERENT id spaces — never joinable by id


def test_bridge_dup_table_honest_none_but_aliases_served():
    from data.equipment import bridge
    dup = "gic_01_n3_ups_01_p1"                           # one of the 18 dual-view twin groups
    assert bridge.eq_row_for_table(dup) is None           # per-meter facts: honest skip
    assert len(bridge.aliases_for_table(dup)) == 2        # aliases: dup twins included
    assert bridge.eq_row_for_table("no_such_table") is None
    assert bridge.aliases_for_table("no_such_table") == []


def test_alias_index_collisions():
    from data.equipment import bridge
    idx = bridge.alias_index()
    assert len(idx[bridge._norm_alias("Solar Incomer-1")]) == 4      # cross-GIC collision key -> ambiguous
    assert idx[bridge._norm_alias("UPS-07 (600KVA)")] == ["gic_06_n3_ups_07_cl_600_kva_p1"]


# ═══ identity gate (fatal-3) ════════════════════════════════════════════════════════════════════════════════════════
def test_identity_gate_fixtures():
    from data.equipment import bridge
    n = bridge.identity_node("gic_06_n3_ups_07_cl_600_kva_p1")       # 'UPS-07 (600KVA)' ~ UPS-07
    assert n and n["via"] == "equipment" and n["key"] == "ups-07"
    n = bridge.identity_node("gic_16_n9_ahu_panel_11_ng")            # equipment_id = PCC-4A (hosting-panel) REJECTED
    assert n and n["via"] == "reference" and "ahu" in (n["key"] or "")
    assert bridge.identity_node("gic_01_n9_solar_incomer_1_p1") is None    # eq='Solar Plant', ref='PCC-1A' -> neither
    assert bridge.identity_node("gic_19_n7_aw_ex_panel_05_ng") is None     # 'AW' vs 'Air Washer' abbreviation miss
    n = bridge.identity_node("gic_08_n3_ahu_9_p1")                   # 'AHU-9 South' ~ 'AHU-09' (de-zero-pad)
    assert n and n["via"] == "equipment"
    assert bridge.identity_node("gic_01_n3_ups_01_p1") is None       # dup twin -> un-bridgeable


def test_identity_gate_incomer_subset_pinned():
    """PINNED INTENDED (round-2 improvement 5): a '<node> incomer'-shaped meter name token-subset-verifies against
    the unit's own node — 'UPS-07 incomer' gets UPS-07's identity (legitimate for incomers, per real rows)."""
    from data.equipment import bridge
    n = bridge.identity_node("gic_21_n3_ups_07_inc_1_p1")
    assert n and n["key"] == "ups-07"


def test_feeds_fed_by_direction_and_identity_wall():
    from data.equipment import bridge
    fed_by, feeds = bridge.feeds_fed_by("gic_06_n3_ups_07_cl_600_kva_p1")
    assert "PCC-3A" in fed_by                              # source FEEDS target: pcc-3a -> ups-07
    assert "UPS Output Panel P2" in feeds                  # ups-07 -> ups-output-p2
    # REGRESSION (fatal-3): an identity-unverified bay meter NEVER claims its hosting panel's fan-out
    assert bridge.feeds_fed_by("gic_19_n7_aw_ex_panel_05_ng") == ([], [])
    assert bridge.feeds_fed_by("gic_01_n9_solar_incomer_1_p1") == ([], [])
    assert bridge.feeds_fed_by("no_such_table") == ([], [])


# ═══ rosters: knob + allowlist + two-sided guard (real PCC-1 data) ══════════════════════════════════════════════════
def test_roster_knob_off_and_not_allowlisted(monkeypatch):
    edges = _knobs(monkeypatch, enabled="off", allowlist=ALLOW_FULL)
    assert edges.panel_roster(PANEL_TABLE, "outgoing") is None       # kill-switch
    edges = _knobs(monkeypatch, enabled="on", allowlist={})
    assert edges.panel_roster(PANEL_TABLE, "outgoing") is None       # empty allowlist == inert
    assert edges.panel_roster(PANEL_TABLE, "sideways") is None       # bad direction


def test_roster_vetted_gain_serves_richer_directed_set(monkeypatch):
    """Proof (1): the bridged PCC panel serves the RICHER directed member set — mirror order first, vetted extras
    ascending; the dup-twin bay is rosterable; no spare/coupler bay ever appears."""
    edges = _knobs(monkeypatch, enabled="on", allowlist=ALLOW_FULL)
    mirror = _mirror_outgoing(PANEL_CID)
    roster = edges.panel_roster(PANEL_TABLE, "outgoing")
    assert roster == mirror + sorted([_canon(HHF1), _canon(HHF2)])
    assert len(roster) == 10 and _canon("gic_01_n3_ups_01_p1") in roster     # dup twin rosterable via reference_id
    tables = {t for t, in ((r[0],) for r in q(CMD_CATALOG,
              "SELECT table_name FROM registry_lt_mfm WHERE id IN (%s)" % ",".join(map(str, roster))))}
    assert not any(t.startswith("mfm_pefc") or "pqm" in t for t in tables)   # spares/couplers never rostered


def test_roster_unvetted_gain_none(monkeypatch):
    edges = _knobs(monkeypatch, enabled="on", allowlist=ALLOW_UNVETTED)
    assert edges.panel_roster(PANEL_TABLE, "outgoing") is None       # guard (ii): HHFs not vetted -> None


def test_roster_incoming_all_or_nothing_none(monkeypatch):
    """The panel's incoming bays carry pqm_* tables absent from the registry -> guard (iii) all-or-nothing -> None
    (incomers stay mirror-served; a partial roster never sums a subset as a panel total)."""
    edges = _knobs(monkeypatch, enabled="on", allowlist=ALLOW_FULL)
    assert edges.panel_roster(PANEL_TABLE, "incoming") is None


def test_roster_loss_none(monkeypatch):
    """Guard (i) on real data: nodes=[pcc-1a] alone loses the gic_02 mirror members -> None."""
    edges = _knobs(monkeypatch, enabled="on", allowlist=ALLOW_HALF)
    assert edges.panel_roster(PANEL_TABLE, "outgoing") is None


def test_mirror_transpose_semantics(monkeypatch):
    """The incoming guard reads the TRANSPOSE (from_mfm_id WHERE to_mfm_id=panel — exactly incomers_of's verified
    semantics); the outgoing mirror keeps edge order."""
    edges = _knobs(monkeypatch, enabled="on", allowlist={})
    assert edges._mirror_members(PANEL_CID, "incoming") == _mirror_incoming(PANEL_CID) == [17, 19, 164, 166]
    assert edges._mirror_members(PANEL_CID, "outgoing") == _mirror_outgoing(PANEL_CID)


def test_direction_sanity_real_pcc(monkeypatch):
    """Proof (4): on the real PCC panel the incomers are transformer/HT/solar class and the outgoers are loads."""
    edges = _knobs(monkeypatch, enabled="on", allowlist=ALLOW_FULL)
    from data.registry.lt_mfm import registry_rows
    by_id = {r["id"]: r for r in registry_rows()}
    out_tables = [by_id[i]["table"] for i in edges.panel_roster(PANEL_TABLE, "outgoing")]
    assert all(("ups" in t) or ("bpdb" in t) or ("hhf" in t) for t in out_tables)        # loads / feeders
    in_tables = [by_id[i]["table"] for i in _mirror_incoming(PANEL_CID)]                 # incoming stays mirror-served
    assert all(("transformer" in t) or ("solar" in t) for t in in_tables)                # supply side


def test_roster_synthetic_empty_mirror_and_guards(monkeypatch):
    """Synthetic loss/vetted-gain/all-or-nothing on a preloaded empty-mirror panel: extras serve ONLY when vetted;
    equipment_parents() greens ONLY the guard-passing allowlisted panel."""
    from data.equipment import db as eqdb
    allow = {"syn_panel": {"nodes": ["syn-node"], "extra_ok": ["syn_child_a", "syn_child_b"]}}
    edges = _knobs(monkeypatch, enabled="on", allowlist=allow)
    edges._CACHE["reg_by_table"] = {"syn_panel": 9000, "syn_child_a": 9001, "syn_child_b": 9002}
    edges._CACHE["mirror_edges"] = []                                 # EMPTY mirror: 73 such meters exist for real
    edges._CACHE["nodes_by_key"] = {"syn-node": 500}
    bays = {"syn_child_a": [{"id": "1", "role": "outgoing", "table_name": "syn_child_a", "reference_id": "500"}],
            "syn_child_b": [{"id": "2", "role": "outgoing", "table_name": "syn_child_b", "reference_id": "500"}],
            "syn_spare": [{"id": "3", "role": "spare", "table_name": "syn_spare", "reference_id": "500"}]}
    monkeypatch.setattr(eqdb, "mfm_by_table", lambda: bays)
    assert edges.panel_roster("syn_panel", "outgoing") == [9001, 9002]          # vetted extras, ascending; no spare
    assert edges.equipment_parents() == {9000}
    # unvetted gain: same bays, empty extra_ok -> None
    edges2 = _knobs(monkeypatch, enabled="on", allowlist={"syn_panel": {"nodes": ["syn-node"], "extra_ok": []}})
    edges2._CACHE.update({"reg_by_table": {"syn_panel": 9000, "syn_child_a": 9001, "syn_child_b": 9002},
                          "mirror_edges": [], "nodes_by_key": {"syn-node": 500}})
    assert edges2.panel_roster("syn_panel", "outgoing") is None
    # loss: a mirror member (9099) absent from the bay roster -> None
    edges3 = _knobs(monkeypatch, enabled="on", allowlist=allow)
    edges3._CACHE.update({"reg_by_table": {"syn_panel": 9000, "syn_child_a": 9001, "syn_child_b": 9002},
                          "mirror_edges": [(1, 9000, 9099)], "nodes_by_key": {"syn-node": 500}})
    assert edges3.panel_roster("syn_panel", "outgoing") is None
    # all-or-nothing: one bay table not in the registry -> None
    edges4 = _knobs(monkeypatch, enabled="on", allowlist=allow)
    edges4._CACHE.update({"reg_by_table": {"syn_panel": 9000, "syn_child_a": 9001},                 # _b unbridgeable
                          "mirror_edges": [], "nodes_by_key": {"syn-node": 500}})
    assert edges4.panel_roster("syn_panel", "outgoing") is None


def test_roster_db_error_not_cached(monkeypatch):
    """A transient :5432 blip returns None WITHOUT poisoning the roster cache — the next call serves."""
    from data.equipment import db as eqdb
    edges = _knobs(monkeypatch, enabled="on", allowlist=ALLOW_FULL)
    real = eqdb.mfm_by_table
    monkeypatch.setattr(eqdb, "mfm_by_table", lambda: {})             # the db.py DB-error contract
    assert edges.panel_roster(PANEL_TABLE, "outgoing") is None
    assert (PANEL_TABLE, "outgoing") not in edges._ROSTERS            # failure NOT cached
    monkeypatch.setattr(eqdb, "mfm_by_table", real)
    assert edges.panel_roster(PANEL_TABLE, "outgoing") is not None    # next call retries and serves


def test_knob_latch(monkeypatch):
    """enabled() is LATCHED at first call — a mid-run flip never switches the edge source under live caches."""
    state = {"v": "off"}
    from config import app_config as _ac
    real = _ac.cfg
    monkeypatch.setattr(_ac, "cfg", lambda k, d: state["v"] if k == "equipment.topology.enabled" else real(k, d))
    from data.equipment import edges
    edges.clear_cache()
    assert edges.enabled() is False
    state["v"] = "on"
    assert edges.enabled() is False                                   # latched
    edges.clear_cache()                                               # operational reload re-reads
    assert edges.enabled() is True


# ═══ lt_mfm merge (parent_ids / outgoing_edges / outgoing_feeders) ══════════════════════════════════════════════════
def test_lt_mfm_serves_equipment_roster_when_on(monkeypatch):
    _knobs(monkeypatch, enabled="on", allowlist=ALLOW_FULL)
    from data.registry import lt_mfm
    lt_mfm._CACHE.clear()
    expected = _mirror_outgoing(PANEL_CID) + sorted([_canon(HHF1), _canon(HHF2)])
    assert [cid for cid, _t in lt_mfm.outgoing_edges([PANEL_CID])] == expected
    feeders = lt_mfm.outgoing_feeders(PANEL_CID)
    assert [f["mfm_id"] for f in feeders] == expected
    assert all(f["table_name"] and f["name"] for f in feeders)


def test_lt_mfm_parent_ids_union(monkeypatch):
    """parent_ids = mirror parents UNION allowlisted+guard-passing equipment panels ONLY."""
    from data.equipment import edges
    from data.registry import lt_mfm
    mirror_parents = {int(r[0]) for r in q(CMD_CATALOG, "SELECT DISTINCT from_mfm_id FROM registry_lt_mfm_outgoing")}
    monkeypatch.setattr(edges, "enabled", lambda: True)
    monkeypatch.setattr(edges, "equipment_parents", lambda: {99999})
    lt_mfm._CACHE.clear()
    assert lt_mfm.parent_ids() == mirror_parents | {99999}


def test_lt_mfm_knobs_off_byte_identity(monkeypatch):
    """Proof (2)+(3): at default knobs every accessor is byte-identical to the raw mirror AND performs ZERO
    equipment reads (eq_q + the roster resolver are rigged to explode)."""
    _knobs(monkeypatch, enabled="off", allowlist=ALLOW_FULL)
    from data.equipment import db as eqdb, edges
    from data.registry import lt_mfm

    def boom(*a, **k):
        raise AssertionError("equipment read at knobs-off")

    monkeypatch.setattr(eqdb, "eq_q", boom)
    monkeypatch.setattr(edges, "_resolve", boom)
    lt_mfm._CACHE.clear()
    raw_edges = [(int(r[0]), r[1] or None) for r in q(CMD_CATALOG,
                 f"SELECT o.to_mfm_id, m.table_name FROM registry_lt_mfm_outgoing o "
                 f"JOIN registry_lt_mfm m ON m.id=o.to_mfm_id WHERE o.from_mfm_id IN ({PANEL_CID}) ORDER BY o.id")]
    assert lt_mfm.outgoing_edges([PANEL_CID]) == raw_edges
    raw_feed = [{"mfm_id": int(r[0]), "table_name": r[1], "name": (r[2] or "").strip()} for r in q(CMD_CATALOG,
                f"SELECT o.to_mfm_id, m.table_name, m.name FROM registry_lt_mfm_outgoing o "
                f"JOIN registry_lt_mfm m ON m.id=o.to_mfm_id WHERE o.from_mfm_id={PANEL_CID} ORDER BY o.to_mfm_id")]
    assert lt_mfm.outgoing_feeders(PANEL_CID) == raw_feed
    mirror_parents = {int(r[0]) for r in q(CMD_CATALOG, "SELECT DISTINCT from_mfm_id FROM registry_lt_mfm_outgoing")}
    assert lt_mfm.parent_ids() == mirror_parents


def test_lt_mfm_unbridged_panel_falls_back(monkeypatch):
    """Proof (2): a panel NOT in the allowlist resolves EXACTLY as today even with the feature ON for another panel."""
    _knobs(monkeypatch, enabled="on", allowlist=ALLOW_FULL)
    from data.registry import lt_mfm
    lt_mfm._CACHE.clear()
    other = 318                                                       # pcc_panel_2 — not allowlisted
    raw = [(int(r[0]), r[1] or None) for r in q(CMD_CATALOG,
           f"SELECT o.to_mfm_id, m.table_name FROM registry_lt_mfm_outgoing o "
           f"JOIN registry_lt_mfm m ON m.id=o.to_mfm_id WHERE o.from_mfm_id IN ({other}) ORDER BY o.id")]
    assert lt_mfm.outgoing_edges([other]) == raw


# ═══ data/neuract_live/members merge (live paths monkeypatched — :5433 never touched) ══════════════════════════════
def _stub_meters(monkeypatch, members_mod):
    reg = {PANEL_CID: {"id": PANEL_CID, "name": "PCC-Panel-1", "table_name": PANEL_TABLE}}

    def meter_by(ref):
        try:
            mid = int(ref)
        except (TypeError, ValueError):
            return None
        return reg.get(mid, {"id": mid, "name": f"M{mid}", "table_name": f"t{mid}"})

    monkeypatch.setattr(members_mod, "_meters",
                        type("MetersStub", (), {"meter_by": staticmethod(meter_by),
                                                "table_for": staticmethod(lambda m: (meter_by(m) or {}).get("table_name")),
                                                "name_for": staticmethod(lambda m: (meter_by(m) or {}).get("name"))}))


def test_members_outgoers_use_roster_with_roles(monkeypatch):
    """Proof (1): outgoers_of serves the richer roster with role='outgoing' — role tagging stays in the caller so
    member_scope -> role_filter_for -> select('supply'|'load') is untouched."""
    _knobs(monkeypatch, enabled="on", allowlist=ALLOW_FULL)
    from data.neuract_live import members
    _stub_meters(monkeypatch, members)
    monkeypatch.setattr(members._db, "table_exists", lambda t: False)          # live edge tables never consulted
    got = members.outgoers_of(PANEL_CID)
    assert [m["mfm_id"] for m in got] == _mirror_outgoing(PANEL_CID) + sorted([_canon(HHF1), _canon(HHF2)])
    assert all(m["role"] == "outgoing" for m in got)
    got = members.members_of(PANEL_CID)                                        # same set via the members door
    assert len(got) == 10 and all(m["role"] == "outgoing" for m in got)


def test_members_incomers_fall_back_to_live_semantics(monkeypatch):
    """The panel's incoming roster guard-fails (pqm_* unbridgeable) -> incomers_of serves TODAY's live path
    (from_mfm_id WHERE to_mfm_id=panel), tagged role='incoming' -> select('supply') still picks exactly them."""
    _knobs(monkeypatch, enabled="on", allowlist=ALLOW_FULL)
    from data.neuract_live import members
    _stub_meters(monkeypatch, members)
    monkeypatch.setattr(members._db, "table_exists", lambda t: t == "lt_mfm_outgoing")
    monkeypatch.setattr(members._db, "rows", lambda sql, p=None: [(17,), (19,), (164,), (166,)])
    got = members.incomers_of(PANEL_CID)
    assert [m["mfm_id"] for m in got] == [17, 19, 164, 166]
    assert all(m["role"] == "incoming" for m in got)
    from ems_exec.executor import members as x_members
    pairs = [(m, {}) for m in got + members.outgoers_of(PANEL_CID)]
    assert {m["mfm_id"] for m, _ in x_members.select(pairs, role_filter="supply")} == {17, 19, 164, 166}
    assert all(m["role"] == "outgoing" for m, _ in x_members.select(pairs, role_filter="load"))


def test_members_knob_off_never_touches_equipment(monkeypatch):
    """Proof (3): at knobs-off the members door never consults the roster (spy explodes) and reads live as today."""
    _knobs(monkeypatch, enabled="off", allowlist=ALLOW_FULL)
    from data.equipment import edges
    from data.neuract_live import members

    def boom(*a, **k):
        raise AssertionError("panel_roster consulted at knobs-off")

    monkeypatch.setattr(edges, "panel_roster", boom)
    _stub_meters(monkeypatch, members)
    monkeypatch.setattr(members._db, "table_exists", lambda t: t == "lt_mfm_outgoing")
    monkeypatch.setattr(members._db, "rows", lambda sql, p=None: [(11,), (12,)])
    assert [m["mfm_id"] for m in members.outgoers_of(PANEL_CID)] == [11, 12]
    assert [m["mfm_id"] for m in members.incomers_of(PANEL_CID)] == [11, 12]
