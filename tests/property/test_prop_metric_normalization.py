"""PROPERTY - config.metrics.normalize_metric: closed over METRIC_VOCAB, case/edge-whitespace-insensitive,
alias-faithful. (The metric leg of "changing capitalization must not change page selection".)
  P1  closure: ANY text normalizes to a canonical vocab keyword (never a phrase, never None).
  P2  fixpoint: a vocab keyword normalizes to itself.
  P3  invariance: normalize(x) is invariant under case flips + leading/trailing whitespace - for ANY x.
  P4  alias table: every alias phrase maps to its declared canonical target, and every target is in the vocab.
Every property runs in BOTH metrics.normalize_strict states (T0-6): strict mode retires the substring loops but the
exact tiers + default fallback keep all four invariants intact (the strict_mode fixture fakes flag_on for the key and
no-ops the metric_unresolved telemetry sink so the run stays hermetic)."""
import pytest
from hypothesis import given, strategies as st

from config.metrics import METRIC_ALIASES, METRIC_VOCAB, normalize_metric
from tests.property.gen import edge_mutants, st_junk


@pytest.fixture(scope="module", params=[False, True], ids=["flag_off", "flag_on"])
def strict_mode(request):
    """Both metrics.normalize_strict states. Module-scoped (hypothesis rejects function-scoped fixtures under @given);
    patches config.app_config.flag_on for THIS key only (normalize_metric imports it lazily, so the patch is seen at
    call time) and silences obs.failures.record (strict fallthrough telemetry must not write files per example)."""
    import config.app_config as AC
    import obs.failures as F
    orig_flag, orig_record = AC.flag_on, F.record

    def fake_flag_on(key, default=False, cfg_fn=None):
        if key == "metrics.normalize_strict":
            return request.param
        return orig_flag(key, default, cfg_fn)

    AC.flag_on = fake_flag_on
    F.record = lambda *a, **kw: {}
    yield request.param
    AC.flag_on = orig_flag
    F.record = orig_record


@given(raw=st.one_of(st.none(), st_junk))
def test_p1_closure(strict_mode, raw):
    assert normalize_metric(raw) in METRIC_VOCAB


@given(v=st.sampled_from(list(METRIC_VOCAB)))
def test_p2_vocab_fixpoint(strict_mode, v):
    assert normalize_metric(v) == v


@given(data=st.data())
def test_p3_case_and_edge_whitespace_invariance(strict_mode, data):
    base = data.draw(st.one_of(st_junk,
                               st.sampled_from(list(METRIC_VOCAB)),
                               st.sampled_from(sorted(METRIC_ALIASES))))
    mutant = data.draw(edge_mutants(base))
    assert normalize_metric(mutant) == normalize_metric(base), (
        f"metric normalization changed under case/whitespace: {base!r} -> {normalize_metric(base)!r} but "
        f"{mutant!r} -> {normalize_metric(mutant)!r}")


def test_p4_alias_table_faithful(strict_mode):
    assert METRIC_ALIASES, "alias vocabulary is empty - the property run would be vacuous"
    for phrase, target in METRIC_ALIASES.items():
        assert target in METRIC_VOCAB, f"alias {phrase!r} targets {target!r} which is NOT in METRIC_VOCAB"
        assert normalize_metric(phrase) == target, (
            f"alias {phrase!r} normalized to {normalize_metric(phrase)!r}, expected {target!r}")
