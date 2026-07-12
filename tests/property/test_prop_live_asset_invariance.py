"""LIVE metamorphic PROPERTY — "changing whitespace must not change asset resolution" + "aliases must resolve
identically" against the REAL pinned-seed resolver on :8200:
  L1  a prompt naming a canonical asset resolves to the same mfm_id as the same prompt with the name re-SPELLED
      within its _norm class ('PCC-Panel-1' vs 'pcc panel 1').
  L2  a prompt spelling a PCC panel ALIAS (cmd_catalog.pcc_panel_alias, e.g. 'PCC-1A') resolves to the same mfm_id
      as the canonical panel name.
Non-pins on BOTH sides of a pair count as agreement (a genuinely ambiguous name staying ambiguous is correct); a pin
on one side only, or two different pins, is a failure. Seeded by PBT_SEED, scaled by PBT_LIVE_EXAMPLES.
"""
import os
import random

import pytest

from tests.property.gen import norm_key, rng_name_mutant

pytestmark = pytest.mark.live

SEED = int(os.environ.get("PBT_SEED", "42"))
N = max(1, int(os.environ.get("PBT_LIVE_EXAMPLES", "4")))


def _pin(out):
    return out["asset"]["mfm_id"] if out.get("asset") else None


def test_l1_name_respelling_same_resolution(qwen_live, registry_snapshot):
    from layer1b.resolve.asset_resolve import resolve_asset
    rng = random.Random(SEED)
    by = {}
    for c in registry_snapshot["cands"]:
        by.setdefault(norm_key(c[1]), []).append(c)
    pool = [c for c in registry_snapshot["cands"]
            if c[6] and len(by[norm_key(c[1])]) == 1 and (len(c) <= 9 or c[9])]   # data-bearing, norm-unique, real
    rng.shuffle(pool)
    failures = []
    for row in pool[:N]:
        a = resolve_asset(f"voltage and current for {row[1]}")
        b = resolve_asset(f"voltage and current for {rng_name_mutant(rng, row[1])}")
        if _pin(a) != _pin(b):
            failures.append(f"  {row[1]!r}: canonical pinned {_pin(a)}, respelling pinned {_pin(b)}")
    assert not failures, "asset resolution changed under name respelling:\n" + "\n".join(failures)


def test_l2_pcc_alias_same_resolution(qwen_live):
    from data.db_client import q
    from layer1b.resolve.asset_resolve import resolve_asset
    rng = random.Random(SEED)
    try:
        pairs = [(a, p) for a, p in q("cmd_catalog", "SELECT alias, panel_name FROM pcc_panel_alias") if a and p]
    except Exception as e:
        pytest.skip(f"pcc_panel_alias unavailable: {e}")
    if not pairs:
        pytest.skip("pcc_panel_alias is empty")
    rng.shuffle(pairs)
    failures = []
    for alias, panel in pairs[:N]:
        a = resolve_asset(f"power overview for {alias}")
        b = resolve_asset(f"power overview for {panel}")
        if _pin(a) != _pin(b):
            failures.append(f"  alias {alias!r} pinned {_pin(a)}, canonical {panel!r} pinned {_pin(b)}")
    assert not failures, "alias and canonical name resolved differently:\n" + "\n".join(failures)
