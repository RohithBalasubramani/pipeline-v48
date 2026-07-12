"""Layer 1b column basket — live: card-agnostic generous basket built from the REAL consumer columns, no hallucination.
Post-rewire: 1b reads the neuract gic_* tables served on :5433, keyed by table name. Anchor = GIC-03-N6-AHU-5
(table gic_03_n6_ahu_5_p1). The contract plumbing column is now `timestamp_utc` (excluded from the dictionary)."""
import pytest

from layer1b.basket.col_dict import col_dict, real_table_cols, latest_nonnull
from layer1b.basket.column_basket import build_basket
from layer1b.resolve.asset_candidates import as_asset

AHU5_TABLE = "gic_03_n6_ahu_5_p1"
AHU5 = as_asset([36, "GIC-03-N6-AHU-5", AHU5_TABLE, "", "GIC-03", "AHU", True])


@pytest.mark.live
def test_col_dict_from_real_columns():
    d = col_dict(AHU5_TABLE)           # dictionary keyed by the real table
    cols = {c[0] for c in d}
    assert cols and any(c.startswith("voltage") for c in cols) and any(c.startswith("current") for c in cols)
    assert "timestamp_utc" not in cols and "panel_id" not in cols   # contract plumbing excluded


@pytest.mark.live
def test_real_table_cols_neuract():
    cols = real_table_cols(AHU5_TABLE)
    assert "current_r" in cols and any(c.startswith("voltage") for c in cols)


@pytest.mark.live
def test_basket_live_real_and_relevant():
    b = build_basket("voltage and current health for AHU-5", AHU5)
    assert b["n_columns"] > 5
    real = real_table_cols(AHU5_TABLE)
    assert all(c["column"] in real for c in b["columns"])         # NO hallucinated columns (all real neuract cols)
    names = {c["column"] for c in b["columns"]}
    assert any(n.startswith("voltage") for n in names) or any(n.startswith("current") for n in names)


def test_basket_empty_for_no_asset():
    assert build_basket("x", None)["n_columns"] == 0
