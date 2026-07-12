"""PROPERTY — layer1b's _norm is the normalization "changing whitespace must not change asset resolution" rests on.
norm_mutants are _norm-equal BY CONSTRUCTION, so these assert _norm itself keeps its contract — a regression there
breaks HERE first, before it silently breaks name/alias resolution.
  P1  closure + idempotence: output is pure [a-z0-9]* and a fixed point.
  P2  mutant equality over REAL registry names: every punctuation/whitespace/case respelling keys identically.
"""
import re

from hypothesis import given, strategies as st

from layer1b.resolve.asset_resolve import _norm
from tests.property.gen import norm_mutants, st_junk


@given(s=st.one_of(st_junk, st.text(max_size=60)))
def test_p1_closure_and_idempotence(s):
    out = _norm(s)
    assert re.fullmatch(r"[a-z0-9]*", out), f"_norm leaked non-alnum chars: {out!r}"
    assert _norm(out) == out


@given(data=st.data())
def test_p2_registry_name_respellings_key_identically(registry_snapshot, data):
    name = data.draw(st.sampled_from([c[1] for c in registry_snapshot["cands"] if c[1]]))
    mutant = data.draw(norm_mutants(name))
    assert _norm(mutant) == _norm(name), (
        f"respelling {mutant!r} of registry name {name!r} keys differently: "
        f"{_norm(mutant)!r} != {_norm(name)!r}")
