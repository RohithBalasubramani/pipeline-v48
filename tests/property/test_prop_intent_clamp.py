"""PROPERTY — layer1a.parse.metric_intent_defaults.clamp_metric_intent: BOTH outputs are always vocabulary members,
for ANY model emission, and the intent clamp is case/edge-whitespace-insensitive.
  P1  closure: (metric, intent) ∈ METRIC_VOCAB × INTENT_VOCAB for any inputs (None/junk/mixed).
  P2  intent fixpoint + case invariance: any casing/padding of a vocab intent clamps to that intent.
  P3  unknown intents fall to the default — never leak through.
"""
from hypothesis import given, strategies as st

from config.intents import INTENT_DEFAULT, INTENT_VOCAB
from config.metrics import METRIC_VOCAB
from layer1a.parse.metric_intent_defaults import clamp_metric_intent
from tests.property.gen import edge_mutants, st_junk


@given(metric=st.one_of(st.none(), st_junk), intent=st.one_of(st.none(), st_junk))
def test_p1_closure(metric, intent):
    m, i = clamp_metric_intent(metric, intent)
    assert m in METRIC_VOCAB and i in INTENT_VOCAB


@given(data=st.data())
def test_p2_intent_case_invariance(data):
    intent = data.draw(st.sampled_from(sorted(INTENT_VOCAB)))
    mutant = data.draw(edge_mutants(intent))
    assert clamp_metric_intent("power", mutant)[1] == intent


@given(junk=st_junk)
def test_p3_unknown_intent_defaults(junk):
    if junk.strip().lower() in INTENT_VOCAB:
        return                                                   # drew a real intent — covered by P2
    assert clamp_metric_intent("power", junk)[1] == INTENT_DEFAULT
