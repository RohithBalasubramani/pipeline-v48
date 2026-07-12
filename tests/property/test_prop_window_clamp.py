"""PROPERTY — layer1a.parse.window_default.clamp_window: the time-window leg of "historical prompts produce
historical windows" that is pure code. The clamp may only emit a TIME_WINDOWS preset key or None — an off-vocab or
absent window can never force a fabricated time range (the host keeps its default), and a real preset survives any
casing/padding the model wraps it in.
  P1  closure: any input clamps to a preset key or None.
  P2  preset fixpoint + case invariance: any casing/padding of a preset key clamps to that key.
  P3  the documented none-sentinels ('none', 'null', 'n/a', …) clamp to None in any casing.
  P4  junk (anything that isn't a preset after strip/lower) clamps to None — fail-closed, never a guess.
"""
from hypothesis import given, strategies as st

from config.windows import TIME_WINDOWS
from layer1a.parse.window_default import _NONE_TOKENS, clamp_window
from tests.property.gen import edge_mutants, st_junk


@given(w=st.one_of(st.none(), st_junk))
def test_p1_closure(w):
    got = clamp_window(w)
    assert got is None or got in TIME_WINDOWS


@given(data=st.data())
def test_p2_preset_case_invariance(data):
    key = data.draw(st.sampled_from(sorted(TIME_WINDOWS)))
    mutant = data.draw(edge_mutants(key))
    assert clamp_window(mutant) == key


@given(data=st.data())
def test_p3_none_sentinels(data):
    tok = data.draw(st.sampled_from([t for t in _NONE_TOKENS if t]))
    mutant = data.draw(edge_mutants(tok))
    assert clamp_window(mutant) is None


@given(junk=st_junk)
def test_p4_off_vocab_is_none(junk):
    if junk.strip().lower() in TIME_WINDOWS or junk.strip().lower() in _NONE_TOKENS:
        return
    assert clamp_window(junk) is None
