"""tests/test_twin_redirect.py — dead-twin → live-twin redirect (data/neuract_live/twin.py + members._member_row)."""
from unittest.mock import patch

from data.neuract_live import twin as T
from data.neuract_live import members as M


_ROWS = [
    {"id": 164, "name": "GIC-15-N10-PCC-01 (Transformer-01)", "table": "gic_15_n10_..._sch",
     "table_exists": False, "never_wired": True},
    {"id": 171, "name": "GIC-15-N3-PCC-01 (Transformer-01) [Secure Elite300]", "table": "gic_15_n3_..._se",
     "table_exists": True, "never_wired": False},
    {"id": 17, "name": "GIC-01-N9-Solar Incomer-1", "table": "gic_01_n9_solar_incomer_1_p1",
     "table_exists": True, "never_wired": False},          # live, no dead twin
    {"id": 900, "name": "GIC-30-N7-Spare", "table": "gic_30_n7_spare_se", "table_exists": True, "never_wired": False},
    {"id": 901, "name": "GIC-01-N1-Spare", "table": "gic_01_n1_spare_p1", "table_exists": True, "never_wired": False},
]


def _reg():
    return patch.object(T._reg, "registry_rows", lambda: _ROWS)


def test_twin_key_gic_scoped():
    assert T._twin_key("GIC-15-N10-PCC-01 (Transformer-01)") == "gic-15-pcc-01 (transformer-01)"
    assert T._twin_key("GIC-15-N3-PCC-01 (Transformer-01) [Secure Elite300]") == "gic-15-pcc-01 (transformer-01)"
    # generic descriptor stays GIC-scoped → never cross-matches across GIC groups
    assert T._twin_key("GIC-30-N7-Spare") != T._twin_key("GIC-01-N1-Spare")


def test_dead_twin_redirects_to_live_sibling():
    with _reg():
        assert T.live_twin_table(164) == "gic_15_n3_..._se"


def test_live_meter_not_redirected():
    with _reg():
        assert T.live_twin_table(171) is None            # already live
        assert T.live_twin_table(17) is None             # live, no dead twin


def test_generic_spare_never_cross_matches():
    # a HYPOTHETICAL dead GIC-01 Spare must NOT borrow the GIC-30 Spare's table
    rows = _ROWS + [{"id": 902, "name": "GIC-01-N2-Spare", "table": "gic_01_n2_spare_sch",
                     "table_exists": False, "never_wired": True}]
    with patch.object(T._reg, "registry_rows", lambda: rows):
        # GIC-01-N2-Spare's only same-key live sibling is GIC-01-N1-Spare (id 901), NOT the GIC-30 one
        assert T.live_twin_table(902) == "gic_01_n1_spare_p1"


def test_member_row_applies_redirect_only_when_flag_on():
    m = {"name": "GIC-15-N10-PCC-01 (Transformer-01)", "table_name": "gic_15_n10_..._sch"}
    with patch.object(M._meters, "meter_by", lambda i: m), \
         patch.object(M._meters, "table_for", lambda x: "gic_15_n10_..._sch"), _reg():
        with patch.object(M, "_twin_redirect_on", lambda: False):
            assert M._member_row(164, "incoming")["neuract_table"] == "gic_15_n10_..._sch"   # off = byte-identical
        with patch.object(M, "_twin_redirect_on", lambda: True):
            assert M._member_row(164, "incoming")["neuract_table"] == "gic_15_n3_..._se"      # on = live twin
            assert M._member_row(164, "incoming")["mfm_id"] == 164                            # id/name unchanged
