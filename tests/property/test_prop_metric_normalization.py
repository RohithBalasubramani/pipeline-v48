"""PROPERTY — config.metrics.normalize_metric: closed over METRIC_VOCAB, case/edge-whitespace-insensitive,
alias-faithful. (The metric leg of "changing capitalization must not change page selection".)
  P1  closure: ANY text normalizes to a canonical vocab keyword (never a phrase, never None).
  P2  fixpoint: a vocab keyword normalizes to itself.
  P3  invariance: normalize(x) is invariant under case flips + leading/trailing whitespace — for ANY x.
  P4  alias table: every alias phrase maps to its declared canonical target, and every target is in the vocab.
"""
from hypothesis import given, strategies as st

from config.metrics import METRIC_ALIASES, METRIC_VOCAB, normalize_metric
from tests.property.gen import edge_mutants, st_junk


@given(raw=st.one_of(st.none(), st_junk))
def test_p1_closure(raw):
    assert normalize_metric(raw) in METRIC_VOCAB


@given(v=st.sampled_from(list(METRIC_VOCAB)))
def test_p2_vocab_fixpoint(v):
    assert normalize_metric(v) == v


@given(data=st.data())
def test_p3_case_and_edge_whitespace_invariance(data):
    base = data.draw(st.one_of(st_junk,
                               st.sampled_from(list(METRIC_VOCAB)),
                               st.sampled_from(sorted(METRIC_ALIASES))))
    mutant = data.draw(edge_mutants(base))
    assert normalize_metric(mutant) == normalize_metric(base), (
        f"metric normalization changed under case/whitespace: {base!r} -> {normalize_metric(base)!r} but "
        f"{mutant!r} -> {normalize_metric(mutant)!r}")


def test_p4_alias_table_faithful():
    assert METRIC_ALIASES, "alias vocabulary is empty — the property run would be vacuous"
    for phrase, target in METRIC_ALIASES.items():
        assert target in METRIC_VOCAB, f"alias {phrase!r} targets {target!r} which is NOT in METRIC_VOCAB"
        assert normalize_metric(phrase) == target, (
            f"alias {phrase!r} normalized to {normalize_metric(phrase)!r}, expected {target!r}")
