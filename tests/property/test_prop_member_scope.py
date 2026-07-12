"""PROPERTY — layer1b.resolve.member_scope (the panel reading direction): a prompt naming the supply side (ANY casing,
any surrounding words) reads 'incomer'; a prompt free of every incomer keyword reads 'outgoing' — the default that
keeps the plain panel prompt byte-identical. Vocabulary-driven (app_config row with the code mirror as fallback), so
the generators draw from the SAME loaded vocabulary the function matches against.
"""
from hypothesis import assume, given, strategies as st

from layer1b.resolve.member_scope import INCOMER, OUTGOING, _incomer_keywords, member_scope
from tests.property.gen import edge_mutants

KWS = tuple(_incomer_keywords())
# filler words verified at import to contain NO incomer keyword as a substring (the matcher is substring-based)
SAFE = [w for w in ("please", "show", "voltage", "current", "power", "panel", "report", "overview",
                    "status", "chart", "trend", "daily", "summary", "pcc", "meter")
        if all(k not in w for k in KWS)]
assert len(SAFE) >= 8, "safe filler vocabulary collapsed — incomer keyword list changed shape"


@given(data=st.data())
def test_keyword_present_reads_incomer(data):
    kw = data.draw(st.sampled_from(KWS))
    variant = data.draw(edge_mutants(kw))                        # casing/padding — internal spacing preserved
    pre = data.draw(st.lists(st.sampled_from(SAFE), max_size=4))
    post = data.draw(st.lists(st.sampled_from(SAFE), max_size=4))
    prompt = " ".join(pre + [variant] + post)
    assert member_scope(prompt) == INCOMER, f"{prompt!r} (keyword {kw!r}) did not read incomer"


@given(words=st.lists(st.sampled_from(SAFE), min_size=0, max_size=8))
def test_no_keyword_defaults_outgoing(words):
    prompt = " ".join(words)
    assume(all(k not in f" {prompt.lower()} " for k in KWS))
    assert member_scope(prompt) == OUTGOING


@given(garbage=st.one_of(st.none(), st.integers(), st.floats(allow_nan=True)))
def test_never_raises_on_non_strings(garbage):
    assert member_scope(garbage) in (INCOMER, OUTGOING)
