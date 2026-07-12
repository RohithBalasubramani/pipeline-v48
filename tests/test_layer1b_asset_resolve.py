"""Layer 1b asset resolution — unit + live (confident / ambiguous / picker round-trip).
CANONICAL id-space (2026-07-04 streamline): candidates come from the cmd_catalog registry_* mirror of the canonical
neuract registry (lt_mfm ⋈ types ⋈ asset; data/registry/lt_mfm.py), id = lt_mfm.id. Rows are 9-element
[id, name, table, mfm_type_id, load_group, class, has_data, has_feeders, never_wired].
Anchor = GIC-03-N6-AHU-5 (canonical lt_mfm.id 36, table gic_03_n6_ahu_5_p1)."""
import pytest

from layer1b.resolve.asset_candidates import asset_candidates, as_asset
from layer1b.resolve.asset_resolve import resolve_asset
from layer1b.resolve.candidate_list import for_picker
from layer1b.schema import validate_layer1b_output, build_layer1b_output

AHU5_ID = 36
AHU5_NAME = "GIC-03-N6-AHU-5"
AHU5_TABLE = "gic_03_n6_ahu_5_p1"


@pytest.mark.live
def test_asset_candidates_live():
    cands = asset_candidates()
    assert len(cands) > 50
    assert all(len(c) >= 9 for c in cands)                       # [id,...,has_data,has_feeders,never_wired]
    by_id = {int(c[0]): c for c in cands}
    row = by_id[AHU5_ID]
    assert row[1] == AHU5_NAME and row[2] == AHU5_TABLE          # canonical lt_mfm row → neuract gic table
    assert isinstance(row[6], bool)                              # has_data flag present (not dropped)
    # AUDIT-3 acceptance: the PCC panels resolve at their CANONICAL ids with feeders + data-via-feeders
    for pid in (317, 318, 319, 320):
        assert by_id[pid][5] == "Panel" and by_id[pid][6] is True and by_id[pid][7] is True
    # Transformer-01 = canonical 171, single meter (no outgoing edge), its own live table
    assert by_id[171][7] is False and by_id[171][6] is True


def test_as_asset_shape():
    a = as_asset([36, AHU5_NAME, AHU5_TABLE, "", "GIC-03", "AHU", True])
    assert a["mfm_id"] == 36 and a["class"] == "AHU" and a["has_data"] is True


def test_for_picker_shape():
    cands = [{"mfm_id": 1, "name": "UPS-01", "class": "UPS", "load_group": "x", "has_data": True}]
    assert for_picker(cands)[0]["mfm_id"] == 1


@pytest.mark.live
def test_resolve_confident_live():
    r = resolve_asset("voltage and current health for AHU-5")
    assert r["how"] == "AI" and r["asset"]["mfm_id"] == AHU5_ID and r["asset"]["class"] == "AHU"


@pytest.mark.live
def test_resolve_ambiguous_live():
    r = resolve_asset("battery health and backup autonomy")
    assert r["how"] == "ambiguous" and r["candidates"]
    assert all(c["class"] == "UPS" for c in r["candidates"])          # all of the inferred class


@pytest.mark.live
def test_resolve_picker_roundtrip():
    r = resolve_asset("voltage and current health", asset_id_override=str(AHU5_ID))
    assert r["how"] == "user-choice" and r["asset"]["mfm_id"] == AHU5_ID


def test_validate_ambiguous_needs_candidates():
    out = build_layer1b_output({"asset": None, "how": "ambiguous", "candidates": []}, {})
    assert validate_layer1b_output(out)   # flagged: ambiguous with no candidate_list
