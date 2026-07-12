"""LIVE metamorphic PROPERTY — "changing capitalization/whitespace must not change page selection" against the REAL
pinned-seed router on :8200 (llm.seed + temperature 0: the SAME prompt is reproducible; these mutants check the model
treats a re-CASED / re-SPACED prompt as the same request). A failure here is a REAL routing instability (a near-tie
flip) — exactly what this property exists to catch.

Scale: PBT_LIVE_EXAMPLES base prompts (default 4) × 2 mutants each ⇒ ~3×N router calls. Seeded by PBT_SEED.
"""
import os
import random

import pytest

from tests.property.gen import rng_prompt_mutant

pytestmark = pytest.mark.live

SEED = int(os.environ.get("PBT_SEED", "42"))
N = max(1, int(os.environ.get("PBT_LIVE_EXAMPLES", "4")))

BASES = [
    "real-time monitoring of PCC-Panel-1",
    "voltage and current for PCC-Panel-2",
    "dg fuel efficiency overview",
    "ups battery autonomy status",
    "transformer thermal life summary",
    "harmonics and power quality for PCC-Panel-3",
]


def test_case_whitespace_page_stability(qwen_live):
    from layer1a.route import route
    rng = random.Random(SEED)
    failures = []
    for base in BASES[:N]:
        ref = route(base)["page_key"]
        for _ in range(2):
            mutant = rng_prompt_mutant(rng, base)
            got = route(mutant)["page_key"]
            if got != ref:
                failures.append(f"  {base!r} -> {ref}\n  {mutant!r} -> {got}")
    assert not failures, "page selection changed under case/whitespace mutation:\n" + "\n".join(failures)
