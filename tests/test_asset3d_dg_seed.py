"""DG 3D seed (scripts/seed_dg_asset3d.py) + generic reason-template seeds — sweep DEFECT K / c60 closure.

Verifies the DB rows the sweep flagged as missing (fullsweep_20260706_004334 page 11, card 60 Engine 3D Callout
Viewer: 'neuract lt_asset_3d/asset_3d_model 0 rows while dg-final-v2 registered+glb exists → avoidable blank'):
  · cmd_catalog.reason_template carries the generic sweep causes (db/seed_reason_templates_sweep.sql + no_asset_3d);
  · neuract.lt_asset_3d carries the REAL dg models and ONLY generator meters carry the tier-1 override;
  · the served GLB file physically exists in the web media root (host/web/public/media) and is a real binary glTF.
neuract checks SKIP (never fail) when the :5433 tunnel is down — the seed is DB state, not code under test."""
import os

import pytest

_V48 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MEDIA = os.path.normpath(os.path.join(_V48, "host", "web", "public", "media"))


def _neuract():
    from config.databases import DATA_DB
    from data.db_client import pg_connect
    try:
        return pg_connect(DATA_DB)
    except Exception as e:
        pytest.skip(f"neuract :5433 tunnel unreachable ({type(e).__name__}) — seed-state checks skipped")


# ── cmd_catalog: the generic sweep reason templates (local :5432, same dependency as the rest of the suite) ─────────
def test_generic_sweep_reason_templates_seeded():
    from config.reason_templates import all_templates
    t = all_templates()
    for cause in ("quantity_mismatch", "const_no_source", "unbound_by_emit", "no_3d_model",
                  "event_register_absent", "no_asset_3d"):
        assert cause in t and t[cause].strip(), f"reason_template row missing/empty for {cause!r}"
    # the no-3D sentences are the honest-blank surface for unseeded assets — they must read as 3D reasons
    assert "3D model" in t["no_3d_model"] and "3D model" in t["no_asset_3d"]
    # unbound_by_emit is rendered via reason(metric=slot) in layer2/build.py — keep the placeholder
    assert "{metric}" in t["unbound_by_emit"]


# ── neuract: the seeded catalog + the generator-only override binding ───────────────────────────────────────────────
def test_lt_asset_3d_dg_rows_seeded():
    from config.databases import DATA_SCHEMA
    conn = _neuract()
    try:
        with conn.cursor() as c:
            c.execute(f"SELECT key, file FROM {DATA_SCHEMA}.lt_asset_3d WHERE key IN ('dg-final-v2','dg-v1')")
            rows = dict(c.fetchall())
    finally:
        conn.close()
    assert rows.get("dg-final-v2") == "3d/glb/dg_final_v2.glb"
    assert rows.get("dg-v1") == "3d/glb/DG_v1.glb"


def test_override_binds_generators_only():
    from config.databases import DATA_SCHEMA
    conn = _neuract()
    try:
        with conn.cursor() as c:
            c.execute(f"SELECT m.name FROM {DATA_SCHEMA}.lt_mfm m "
                      f"JOIN {DATA_SCHEMA}.lt_asset_3d a ON a.id = m.asset_3d_override_id "
                      f"WHERE a.key = 'dg-final-v2' ORDER BY m.id")
            bound = [r[0] for r in c.fetchall()]
    finally:
        conn.close()
    assert len(bound) == 12                                        # DG-1..6 MFM + GIC-28 DG-01..06 [Jackson]
    assert all("DG" in n for n in bound)
    # the NON-generator DG-side meters must stay unbound (a generator GLB on a feeder/incomer would be wrong-model)
    assert not any(("OG" in n) or ("Incomer" in n) for n in bound)


# ── media: the served file is the REAL GLB (magic 'glTF'), not a ghost path ─────────────────────────────────────────
def test_dg_glb_present_in_media_root():
    p = os.path.join(_MEDIA, "3d", "glb", "dg_final_v2.glb")
    if not os.path.isdir(_MEDIA):
        pytest.skip("web media root not present on this checkout")
    assert os.path.isfile(p), "dg_final_v2.glb missing from the web media root — seeded url would 404"
    with open(p, "rb") as f:
        assert f.read(4) == b"glTF"                                # binary-glTF magic — a real model file
    assert os.path.getsize(p) > 100_000


# ── the 4-tier resolve end-to-end: a DG meter binds the real model; a panel meter still honest-degrades ─────────────
def test_emit_asset_3d_resolves_dg_and_degrades_others():
    conn = _neuract()                                              # emit reads live neuract — same skip guard
    conn.close()
    from layer2.emit.metadata.asset_3d import emit_asset_3d
    dg = emit_asset_3d({"mfm_id": 2, "name": "DG-1 MFM"}, "diesel-generator-asset-dashboard/engine-cooling")
    obj = dg.get("object") or {}
    assert obj.get("slug") == "dg-final-v2"
    assert (obj.get("url") or "").endswith("/media/3d/glb/dg_final_v2.glb")
    # a panel meter with no per-MFM/type binding resolves the TIER-4 GLOBAL DEFAULT on an overview page —
    # viewer.default_asset_3d_key='pcc1a-v1' resolves since scripts/seed_pcc1a_asset3d.py landed the catalog
    # row (2026-07-15, audit 14 F3: the dead default key silently killed the fallback for ~189 records)
    other = emit_asset_3d({"mfm_id": 317, "name": "PCC-Panel-1"}, "panel-overview-shell/real-time-monitoring")
    oobj = other.get("object") or {}
    assert oobj.get("slug") == "pcc1a-v1"
    assert (oobj.get("url") or "").endswith("/media/3d/glb/PCC1A_v1.glb")
    # tier 4 is INDIVIDUAL/OVERVIEW page-types only — elsewhere the honest degrade stands (never a guessed GLB)
    gated = emit_asset_3d({"mfm_id": 317, "name": "PCC-Panel-1"},
                          "panel-overview-shell/real-time-monitoring", page_type="topology")
    assert (gated.get("object") or None) is None
    assert "3D model" in (gated.get("reason") or "")
