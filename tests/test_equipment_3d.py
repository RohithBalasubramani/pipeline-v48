"""tests/test_equipment_3d.py — stream D: the equipment kit-preview 3D fallback (LOCAL :5432 only; passes with the
:5433 tunnel DOWN — every neuract read in the resolve chain is monkeypatched deterministic-miss where it matters).

Proves the four task gates:
  1. the neuract lt_asset_3d 4-tier chain STILL WINS whenever it binds (tier 5 never consulted);
  2. the kit-preview fallback fires for an identity-verified node with a locally-present GLB;
  3. no match / unverified identity / knob OFF → today's object=null behaviour, byte-identical;
  4. nothing in the chain ever raises on a DB outage.

Stream A's data/equipment/bridge.py may not exist yet (wave-1 parallel): every test that needs identity_node injects
a STUB module into sys.modules — the tier imports it lazily, so the stub wins either way."""
import sys
import types

import pytest

import layer2.emit.metadata.asset_3d as m3d
from data.equipment import db as eqdb
from data.equipment import kitpreview as kp
from ems_exec.renderers import asset_3d as r3d

PAGE_IND = "individual-feeder-meter-shell/energy-power"        # → page_type 'individual' (code map, DB-independent)


# ── helpers ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def _cfg_over(monkeypatch, over):
    """Overlay app_config.cfg with `over` (everything else falls through to the real fn)."""
    from config import app_config as _ac
    real = _ac.cfg

    def fake(key, default):
        return over[key] if key in over else real(key, default)

    monkeypatch.setattr(_ac, "cfg", fake)


def _stub_bridge(monkeypatch, node, calls=None):
    """Inject a fake data.equipment.bridge whose identity_node returns `node` (records calls)."""
    mod = types.ModuleType("data.equipment.bridge")

    def identity_node(table):
        if calls is not None:
            calls.append(table)
        return node

    mod.identity_node = identity_node
    monkeypatch.setitem(sys.modules, "data.equipment.bridge", mod)


def _neuract_miss(monkeypatch):
    """Make the 4 lt_asset_3d tiers deterministically MISS (also proves :5433 independence)."""
    monkeypatch.setattr(m3d, "_one", lambda sql: None)


def _pcc1a():
    """(equipment node id, glb_file) for the real pcc-1a catalog row — read on :5432 (tests are single-door exempt)."""
    nid = eqdb.eq_q("SELECT id FROM equipment.equipment WHERE key='pcc-1a'")[0][0]
    glb = eqdb.eq_q("SELECT glb_file FROM equipment.kitpreview_cat_asset WHERE slug='pcc-1a'")[0][0]
    return int(nid), glb


def _node(key, panel_type=None, asset_type=None, node_id=0):
    return {"node_id": node_id, "via": "equipment", "name": key, "key": key, "distribution_panel": bool(panel_type),
            "metered": True, "group": "", "asset_type_code": asset_type, "panel_type_code": panel_type}


# ── resolve_model: the rule ranking over the REAL local rows ─────────────────────────────────────────────────────────
def test_resolve_model_for_key_wins():
    # pcc-1a is BOTH for_key-ruled and (as a panel) type-ruled — for_key must win.
    out = kp.resolve_model("pcc-1a", "distribution_panel", None, "", "individual")
    assert out and out["slug"] == "pcc-1a" and out["glb_file"]
    assert isinstance(out["default_overrides"], dict) and out["default_overrides"]
    assert isinstance(out["rule_preset"], dict)                    # the pcc-1a rule carries its own preset, SEPARATE


def test_resolve_model_rating_variant_beats_wildcard():
    rated = kp.resolve_model(None, "lt_panel", None, "630A", "individual")
    wild = kp.resolve_model(None, "lt_panel", None, "", "individual")
    unknown = kp.resolve_model(None, "lt_panel", None, "9999A", "individual")
    assert rated and wild and rated["slug"] != wild["slug"]        # 630A variant ≠ the type default
    assert unknown and unknown["slug"] == wild["slug"]             # unknown rating falls to the '' wildcard


def test_resolve_model_page_type_scoped():
    ind = kp.resolve_model(None, None, "ahu", "", "individual")
    ovr = kp.resolve_model(None, None, "ahu", "", "overview")
    assert ind and ovr and ind["slug"] != ovr["slug"]              # ahu vs ahu-overview


def test_resolve_model_default_panel_model_individual_panels_only():
    # an unmatched PANEL type on an 'individual' page falls to app_kv default_panel_model …
    out = kp.resolve_model(None, "no_such_panel_type", None, "", "individual")
    assert out and out["slug"] == "1000xacb-panel"
    # … but NOT on overview, and NOT for an asset-typed (non-panel) node
    assert kp.resolve_model(None, "no_such_panel_type", None, "", "overview") is None
    assert kp.resolve_model(None, None, "no_such_asset_type", "", "individual") is None


def test_resolve_model_accessors_and_misses():
    assert kp.resolve_model(None, None, None, "", "individual") is None
    vd = kp.viewer_defaults()
    assert isinstance(vd, dict) and "toneMap" in vd                # the real app_kv baseline
    assert kp.config_rating(128) == "660A"                         # the ONE populated rating row (bpdb-01)
    assert kp.config_rating(99999999) is None
    assert kp.config_rating("not-an-id") is None


def test_resolve_model_never_raises_on_outage(monkeypatch):
    def boom(sql):
        raise RuntimeError("db down")
    monkeypatch.setattr(eqdb, "eq_q", boom)
    assert kp.resolve_model("pcc-1a", None, None, "", "individual") is None
    assert kp.viewer_defaults() == {}
    assert kp.config_rating(128) is None


# ── gate 1: neuract lt_asset_3d still WINS when it binds ────────────────────────────────────────────────────────────
def test_neuract_tier_wins_over_kitpreview(monkeypatch, tmp_path):
    _cfg_over(monkeypatch, {"equipment.kitpreview.enabled": "on",
                            "equipment.kitpreview.media_base": str(tmp_path)})
    calls = []
    _stub_bridge(monkeypatch, _node("pcc-1a", panel_type="distribution_panel"), calls)
    _neuract_miss(monkeypatch)                                     # :5433-independent (rating read fail-opens too)
    monkeypatch.setattr(m3d, "_tier_override", lambda mid: ("dg", "DG Set", "3d/glb/DG_v1.glb"))
    out = m3d.emit_asset_3d({"mfm_id": 42, "name": "DG-1", "table": "gic_x"}, PAGE_IND)
    assert out["object"]["slug"] == "dg" and out["object"]["url"].endswith("DG_v1.glb")
    assert calls == []                                             # tier 5 NEVER consulted when a neuract tier binds


# ── gate 2: the fallback fires for a verified node with a locally-present GLB ───────────────────────────────────────
def test_kitpreview_fallback_fires(monkeypatch, tmp_path):
    nid, glb = _pcc1a()
    f = tmp_path / glb
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(b"glTF")
    _cfg_over(monkeypatch, {"equipment.kitpreview.enabled": "on",
                            "equipment.kitpreview.media_base": str(tmp_path)})
    _stub_bridge(monkeypatch, _node("pcc-1a", panel_type="distribution_panel", node_id=nid))
    _neuract_miss(monkeypatch)

    out = m3d.emit_asset_3d({"mfm_id": 42, "name": "PCC-1A", "table": "gic_pcc_1a"}, PAGE_IND)
    obj = out["object"]
    assert obj["slug"] == "pcc-1a" and obj["url"].endswith(glb)
    # the SERVED url — never the checked FS path. Absolute OR root-relative: since 2026-07-12 the web origin itself
    # serves /media/ (legacy EMS media service retired), so the default base is '/media/'.
    assert obj["url"].startswith(("http", "/media/"))
    assert str(tmp_path) not in obj["url"]
    assert isinstance(obj["preset"], dict) and obj["preset"]       # default_overrides ⊕ rule.preset merged
    assert isinstance(obj["template"], dict)                       # pcc-1a carries a KPI-overlay template
    assert out["viewer"]["pageType"] == "individual"

    # renderer envelope: object verbatim + the ADDITIVE top-level template key + preset honoured in viewer
    env = r3d.render({"mfm_id": 42, "name": "PCC-1A"}, {"id": 60},
                     {"asset_table": "gic_pcc_1a", "page_key": PAGE_IND})
    assert env["object"]["slug"] == "pcc-1a"
    assert env["template"] == obj["template"]
    assert env["viewer"].get("edges")                              # a merged-preset leaf reached the viewer look


# ── gate 3: no match / unverified / knob off → today's object=null, byte-identical ──────────────────────────────────
def test_no_rule_match_is_null_as_today(monkeypatch, tmp_path):
    _cfg_over(monkeypatch, {"equipment.kitpreview.enabled": "on",
                            "equipment.kitpreview.media_base": str(tmp_path)})
    _stub_bridge(monkeypatch, _node("no-such-key"))                # no key/type rule can match
    _neuract_miss(monkeypatch)
    out = m3d.emit_asset_3d({"mfm_id": 42, "name": "X", "table": "gic_x"}, PAGE_IND)
    assert "object" not in out and out.get("reason") and "cause" not in out


def test_identity_unverified_is_null(monkeypatch, tmp_path):
    _cfg_over(monkeypatch, {"equipment.kitpreview.enabled": "on",
                            "equipment.kitpreview.media_base": str(tmp_path)})
    _stub_bridge(monkeypatch, None)                                # the 43/183 honest-None meters
    _neuract_miss(monkeypatch)
    out = m3d.emit_asset_3d({"mfm_id": 42, "name": "AW Exhaust-05", "table": "gic_aw_05"}, PAGE_IND)
    assert "object" not in out and out.get("reason")


def test_knob_off_byte_identical_and_tier_inert(monkeypatch):
    _neuract_miss(monkeypatch)
    baseline = m3d.emit_asset_3d({"mfm_id": 42, "name": "PCC-1A", "table": "gic_pcc_1a"}, PAGE_IND)  # today's path
    calls = []
    _stub_bridge(monkeypatch, _node("pcc-1a", panel_type="distribution_panel"), calls)
    _cfg_over(monkeypatch, {"equipment.kitpreview.enabled": "off"})               # the shipped default, explicit
    out = m3d.emit_asset_3d({"mfm_id": 42, "name": "PCC-1A", "table": "gic_pcc_1a"}, PAGE_IND)
    assert out == baseline and "object" not in out                 # byte-identical reason dict
    assert calls == []                                             # identity gate never even consulted


def test_default_deny_media_base(monkeypatch, tmp_path):
    nid, glb = _pcc1a()
    _stub_bridge(monkeypatch, _node("pcc-1a", panel_type="distribution_panel", node_id=nid))
    _neuract_miss(monkeypatch)
    # (a) unset root → DENY with the specific per-leaf cause
    _cfg_over(monkeypatch, {"equipment.kitpreview.enabled": "on", "equipment.kitpreview.media_base": ""})
    out = m3d.emit_asset_3d({"mfm_id": 42, "name": "PCC-1A", "table": "gic_pcc_1a"}, PAGE_IND)
    assert "object" not in out and out["cause"] == "glb_not_in_media_root"
    # (b) remote-looking root → DENY
    _cfg_over(monkeypatch, {"equipment.kitpreview.enabled": "on",
                            "equipment.kitpreview.media_base": "http://10.90.200.91/media/"})
    out = m3d.emit_asset_3d({"mfm_id": 42, "name": "PCC-1A", "table": "gic_pcc_1a"}, PAGE_IND)
    assert "object" not in out and out["cause"] == "glb_not_in_media_root"
    # (c) readable dir but the file is ABSENT → DENY
    _cfg_over(monkeypatch, {"equipment.kitpreview.enabled": "on",
                            "equipment.kitpreview.media_base": str(tmp_path)})
    out = m3d.emit_asset_3d({"mfm_id": 42, "name": "PCC-1A", "table": "gic_pcc_1a"}, PAGE_IND)
    assert "object" not in out and out["cause"] == "glb_not_in_media_root"
    # …and the renderer surfaces that cause on the per-leaf gap channel
    env = r3d.render({"mfm_id": 42, "name": "PCC-1A"}, {"id": 60},
                     {"asset_table": "gic_pcc_1a", "page_key": PAGE_IND})
    from ems_exec.executor.fill import GAPS_KEY
    assert env["object"] is None and env[GAPS_KEY][0]["cause"] == "glb_not_in_media_root"
    assert "template" not in env                                   # additive key OMITTED on miss (cert rule 2)


# ── gate 4: never raises on outage / half-built bridge ──────────────────────────────────────────────────────────────
def test_never_raises_on_outage(monkeypatch, tmp_path):
    _cfg_over(monkeypatch, {"equipment.kitpreview.enabled": "on",
                            "equipment.kitpreview.media_base": str(tmp_path)})
    _stub_bridge(monkeypatch, _node("pcc-1a", panel_type="distribution_panel"))
    _neuract_miss(monkeypatch)

    def boom(sql):
        raise RuntimeError("db down")
    monkeypatch.setattr(eqdb, "eq_q", boom)                        # the :5432 side goes dark mid-request
    out = m3d.emit_asset_3d({"mfm_id": 42, "name": "PCC-1A", "table": "gic_pcc_1a"}, PAGE_IND)
    assert "object" not in out and out.get("reason")               # honest degrade, no raise


def test_broken_bridge_never_raises(monkeypatch, tmp_path):
    _cfg_over(monkeypatch, {"equipment.kitpreview.enabled": "on",
                            "equipment.kitpreview.media_base": str(tmp_path)})
    _neuract_miss(monkeypatch)
    mod = types.ModuleType("data.equipment.bridge")                # a half-built wave-1 bridge: attribute MISSING

    def _raiser(table):
        raise AttributeError("half-built")
    mod.identity_node = _raiser
    monkeypatch.setitem(sys.modules, "data.equipment.bridge", mod)
    out = m3d.emit_asset_3d({"mfm_id": 42, "name": "PCC-1A", "table": "gic_pcc_1a"}, PAGE_IND)
    assert "object" not in out and out.get("reason")
    monkeypatch.setitem(sys.modules, "data.equipment.bridge", None)   # import → ImportError branch
    out = m3d.emit_asset_3d({"mfm_id": 42, "name": "PCC-1A", "table": "gic_pcc_1a"}, PAGE_IND)
    assert "object" not in out and out.get("reason")


def test_tier_traversal_guard(monkeypatch, tmp_path):
    _cfg_over(monkeypatch, {"equipment.kitpreview.media_base": str(tmp_path)})
    outside = tmp_path.parent / "outside.glb"
    outside.write_bytes(b"x")
    assert m3d._kitpreview_local_glb("../outside.glb") is None     # traversal outside the root → DENY
