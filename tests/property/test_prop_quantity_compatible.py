"""PROPERTY — domain.quantity_class.compatible() is the reproducibility-critical anti-fabrication gate (a False
blanks a real leaf). These properties pin the invariants the T2.2 re-grounding (S2-S5) must NOT break; the corpus
replay is the empirical gate, these are the algebraic one. [T2.2-S1]

Invariants (from compatible()'s own contract):
  I1  UNCLASSIFIED NEVER BLANKS: None on either side -> compatible (no false positive on unfamiliar spellings).
  I2  SAME CLASS NEVER BLANKS: compatible(c, c) for every c.
  I3  WEAK-vs-WEAK compatible.
  I4  WEAK vs a HARD DIMENSIONAL class is INCOMPATIBLE in BOTH directions ('%' can never BE kW/V/degC).
  I5  WEAK vs a non-dimensional non-weak class is compatible (a '%' could be any percent-semantic).
  I6  TWO DISTINCT HARD-DIMENSIONAL classes (no grant pair) are incompatible.
  I7  ORDERED GRANT PAIRS are directional: the granted (slot, source) is compatible; the reverse is only compatible
      if it is ALSO a listed pair.
  I8  TOKEN-EXACTNESS: name_class never classifies a vocab token that appears only as a non-boundary substring.
"""
from hypothesis import given, strategies as st

import domain.quantity_class as QC

_WEAK = sorted(QC._weak())                       # ['percent']
_DIM = sorted(QC._dimensional())                 # current/energy/frequency/power/temperature/voltage
_PAIRS = QC._compatible_pairs()                  # {('current','deviation-spread'), ('voltage','deviation-spread')}
_NONDIM_NONWEAK = ["deviation-spread", "score-index", "load-factor", "ratio-generic"]
_ALL = _WEAK + _DIM + _NONDIM_NONWEAK
_cls = st.sampled_from(_ALL)


@given(x=st.one_of(_cls, st.none(), st.text(max_size=6)))
def test_I1_none_side_always_compatible(x):
    assert QC.compatible(None, x) and QC.compatible(x, None)


@given(c=_cls)
def test_I2_same_class_compatible(c):
    assert QC.compatible(c, c)


@given(a=st.sampled_from(_WEAK), b=st.sampled_from(_WEAK))
def test_I3_weak_weak_compatible(a, b):
    assert QC.compatible(a, b)


@given(w=st.sampled_from(_WEAK), d=st.sampled_from(_DIM))
def test_I4_weak_vs_dimensional_incompatible_both_ways(w, d):
    assert not QC.compatible(w, d)
    assert not QC.compatible(d, w)


@given(w=st.sampled_from(_WEAK), n=st.sampled_from(_NONDIM_NONWEAK))
def test_I5_weak_vs_nondimensional_compatible(w, n):
    # skip the decreed grant pairs (they are compatible by other means, still fine here)
    assert QC.compatible(w, n) and QC.compatible(n, w)


@given(a=st.sampled_from(_DIM), b=st.sampled_from(_DIM))
def test_I6_distinct_dimensionals_incompatible(a, b):
    if a == b or (a.lower(), b.lower()) in _PAIRS or (b.lower(), a.lower()) in _PAIRS:
        return
    assert not QC.compatible(a, b)


def test_I7_grant_pairs_directional():
    for slot, source in _PAIRS:
        assert QC.compatible(slot, source), f"granted pair {slot}<-{source} must be compatible"
        if (source.lower(), slot.lower()) not in _PAIRS:
            # the reverse is a hard-dimensional-vs-stat breach unless separately granted
            rev = QC.compatible(source, slot)
            assert rev is False or slot.lower() in QC._weak() or source.lower() in QC._weak()


@given(junk=st.sampled_from(["graph5", "paragraph", "currentless_note", "voltageometry_label", "powerpoint"]))
def test_I8_name_class_token_exact_not_substring(junk):
    # 'graph' contains no vocab token as a WHOLE token; 'paragraph' embeds no class; a label that merely CONTAINS a
    # class token mid-word must not classify to that dimension (token-exact, not substring).
    cls = QC.name_class(junk)
    assert cls not in _DIM or cls is None      # never a hard dimensional class off a substring accident
