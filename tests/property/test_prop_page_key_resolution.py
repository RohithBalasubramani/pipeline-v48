"""PROPERTY — layer1a.parse.page_key_fallback.resolve_page_key is CLOSED over the candidates and FAIL-CLOSED.

The deterministic half of "changing capitalization must not change page selection": whatever the router model emits,
the resolver may only land on a candidate page or fail closed — never invent, never silently flip to a different page.
  P1  closure: for ANY emission and ANY key list, the resolution is a candidate key or None.
  P2  verbatim identity: an exact candidate key resolves to itself as 'verbatim'.
  P3  case/edge-whitespace mutants of a real key resolve to THAT key or None — NEVER to a DIFFERENT page.
  P4  emissions unrelated to every candidate resolve to None (never a silent keys[0]).
  P5  exhaustive: every live page key round-trips its upper/lower/padded spellings (deterministic, all keys).
"""
import string

from hypothesis import assume, given, strategies as st

from layer1a.parse.page_key_fallback import resolve_page_key
from tests.property.gen import edge_mutants, st_junk

st_slug = st.text(alphabet=string.ascii_lowercase + string.digits + "-/", min_size=1, max_size=30)


@given(pk=st.one_of(st.none(), st_junk, st_slug),
       keys=st.lists(st_slug, min_size=1, max_size=8, unique=True))
def test_p1_closure_over_random_key_lists(pk, keys):
    got, how = resolve_page_key(pk, keys)
    assert got is None or got in keys
    assert how in ("verbatim", "segment", "substring", "missing", "ambiguous", "no_match")


@given(data=st.data())
def test_p2_verbatim_identity(page_snapshot, data):
    keys = page_snapshot["keys"]
    k = data.draw(st.sampled_from(keys))
    assert resolve_page_key(k, keys) == (k, "verbatim")


@given(data=st.data())
def test_p3_case_mutant_never_a_different_page(page_snapshot, data):
    keys = page_snapshot["keys"]
    k = data.draw(st.sampled_from(keys))
    m = data.draw(edge_mutants(k))
    got, how = resolve_page_key(m, keys)
    assert got in (k, None), f"case mutant {m!r} of {k!r} resolved to a DIFFERENT page {got!r} ({how})"


@given(pk=st_junk)
def test_p4_unrelated_emission_fails_closed(page_snapshot, pk):
    keys = page_snapshot["keys"]
    p = pk.strip().lower()
    assume(p)
    assume(all(p not in k.lower() for k in keys))
    assume(all(k.lower().rsplit("/", 1)[-1] != p for k in keys))
    got, how = resolve_page_key(pk, keys)
    assert got is None and how == "no_match"


def test_p5_every_live_key_roundtrips_spellings(page_snapshot):
    keys = page_snapshot["keys"]
    assert len(keys) >= 9                                       # non-vacuous: the code-default allow-list is 18 pages
    for k in keys:
        # recovery is expected when the lowered key is a substring of exactly ONE candidate (itself); a prefix
        # collision (k substring of another key) legally fails closed instead — never resolves elsewhere.
        unique = sum(1 for x in keys if k.lower() in x.lower()) == 1
        for m in (k.upper(), k.lower(), f"  {k}  "):
            got, _how = resolve_page_key(m, keys)
            assert got in (k, None)
            if unique and m.strip() != k:
                assert got == k, f"{m!r} failed to recover to {k!r} despite being uniquely resolvable"
