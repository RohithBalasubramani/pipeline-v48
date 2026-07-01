"""Layer 1b asset resolution — unit + live (confident / ambiguous / picker round-trip).
Post-rewire: candidates come from meta_data_version1.app_devices ⋈ neuract gic_* tables (5433). Rows are 7-element
[id, name, table, mfm_type_id, load_group, class, has_data]. Anchor = GIC-03-N6-AHU-5 (id 36, table gic_03_n6_ahu_5_p1)."""
from layer1b.resolve.asset_candidates import asset_candidates, as_asset
from layer1b.resolve.asset_resolve import resolve_asset
from layer1b.resolve.candidate_list import for_picker
from layer1b.schema import validate_layer1b_output, build_layer1b_output

AHU5_ID = 36
AHU5_NAME = "GIC-03-N6-AHU-5"
AHU5_TABLE = "gic_03_n6_ahu_5_p1"


def test_asset_candidates_live():
    cands = asset_candidates()
    assert len(cands) > 50
    assert all(len(c) >= 7 for c in cands)                       # [id,name,table,mfm_type,load_group,class,has_data,(has_feeders)]
    by_id = {int(c[0]): c for c in cands}
    row = by_id[AHU5_ID]
    assert row[1] == AHU5_NAME and row[2] == AHU5_TABLE          # known asset (app_devices → neuract gic table)
    assert isinstance(row[6], bool)                              # has_data flag present (not dropped)


def test_as_asset_shape():
    a = as_asset([36, AHU5_NAME, AHU5_TABLE, "", "GIC-03", "AHU", True])
    assert a["mfm_id"] == 36 and a["class"] == "AHU" and a["has_data"] is True


def test_for_picker_shape():
    cands = [{"mfm_id": 1, "name": "UPS-01", "class": "UPS", "load_group": "x", "has_data": True}]
    assert for_picker(cands)[0]["mfm_id"] == 1


def test_resolve_confident_live():
    r = resolve_asset("voltage and current health for AHU-5")
    assert r["how"] == "AI" and r["asset"]["mfm_id"] == AHU5_ID and r["asset"]["class"] == "AHU"


def test_resolve_ambiguous_live():
    r = resolve_asset("battery health and backup autonomy")
    assert r["how"] == "ambiguous" and r["candidates"]
    assert all(c["class"] == "UPS" for c in r["candidates"])          # all of the inferred class


def test_resolve_picker_roundtrip():
    r = resolve_asset("voltage and current health", asset_id_override=str(AHU5_ID))
    assert r["how"] == "user-choice" and r["asset"]["mfm_id"] == AHU5_ID


def test_validate_ambiguous_needs_candidates():
    out = build_layer1b_output({"asset": None, "how": "ambiguous", "candidates": []}, {})
    assert validate_layer1b_output(out)   # flagged: ambiguous with no candidate_list
