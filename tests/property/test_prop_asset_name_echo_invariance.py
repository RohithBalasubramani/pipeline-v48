"""PROPERTY — "changing whitespace must not change asset resolution" (the deterministic half): resolve_asset maps the
model's VERBATIM name answer back to the registry through exact → norm-unique → alias, so ANY _norm-equal respelling
of a canonical asset name the model echoes must pin the SAME registry row as the canonical spelling — same mfm_id,
same outcome kind (AI when the meter has data, no_data when it doesn't; never a silently different asset).
"""
import pytest
from hypothesis import given, strategies as st

from tests.property.gen import norm_key, norm_mutants


@pytest.fixture(scope="session")
def unique_named_rows(registry_snapshot):
    """Registry rows whose canonical name is _norm-UNIQUE across the registry (a colliding name is legitimately
    ambiguous — resolution refusing to pin it is correct, so those rows are excluded from THIS invariant) and whose
    table physically exists (a ghost can never be pinned by design [P03])."""
    cands = registry_snapshot["cands"]
    by = {}
    for c in cands:
        by.setdefault(norm_key(c[1]), []).append(c)
    rows = [c for c in cands
            if c[1] and len(by[norm_key(c[1])]) == 1 and (len(c) <= 9 or c[9])]
    assert len(rows) >= 20, "registry snapshot too small — the property run would be vacuous"
    return rows


@given(data=st.data())
def test_norm_equal_echo_pins_the_same_row(resolve_offline, unique_named_rows, data):
    row = data.draw(st.sampled_from(unique_named_rows))
    mutant = data.draw(norm_mutants(row[1]))

    resolve_offline["reply"] = {"names": [mutant], "confident": True}
    out = resolve_offline["resolve"](f"voltage for {mutant}")
    assert out["asset"] is not None, f"respelling {mutant!r} of {row[1]!r} did not resolve at all (how={out['how']})"
    assert out["asset"]["mfm_id"] == int(row[0]), (
        f"respelling {mutant!r} of {row[1]!r} pinned mfm {out['asset']['mfm_id']} != {row[0]}")
    assert out["how"] in ("AI", "no_data")

    resolve_offline["reply"] = {"names": [row[1]], "confident": True}
    ref = resolve_offline["resolve"](f"voltage for {row[1]}")
    assert ref["asset"] is not None and ref["asset"]["mfm_id"] == out["asset"]["mfm_id"]
    assert ref["how"] == out["how"], (
        f"outcome kind changed under respelling: canonical={ref['how']} mutant={out['how']} for {row[1]!r}")
