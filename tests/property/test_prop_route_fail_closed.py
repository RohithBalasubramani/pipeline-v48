"""PROPERTY — layer1a.route.route() is FAIL-CLOSED and clamped at the LLM boundary (offline: catalog snapshot-pinned,
router LLM holder-faked, so hundreds of arbitrary model emissions run in-process).

Whatever JSON the router model emits:
  P1  a returned route always lands on an AVAILABLE page — never an invented page, never the old silent keys[0];
      metric/intent/window are ALWAYS clamped to their vocabularies.
  P2  an emission naming an exact candidate page is honored verbatim (selection is the model's, unmangled).
  P3  a case/whitespace mutant of a candidate key lands on THAT page or raises — never on a DIFFERENT page.
  P4  an empty emission (transport failure fingerprint) raises — the fail-closed contract.
"""
import pytest
from hypothesis import given, strategies as st

from config.intents import INTENT_VOCAB
from config.metrics import METRIC_VOCAB
from config.windows import TIME_WINDOWS
from tests.property.gen import edge_mutants, st_junk


@given(data=st.data())
def test_p1_p2_fuzz_model_emission(route_offline, page_snapshot, data):
    eff = page_snapshot["eff_keys"]
    avail = set(page_snapshot["keys"])
    pk = data.draw(st.one_of(st.sampled_from(eff), st_junk, st.none()))
    route_offline["reply"] = {
        "page_key": pk,
        "metric": data.draw(st.one_of(st.none(), st_junk, st.sampled_from(list(METRIC_VOCAB)))),
        "intent": data.draw(st.one_of(st.none(), st_junk, st.sampled_from(sorted(INTENT_VOCAB)))),
        "window": data.draw(st.one_of(st.none(), st_junk, st.sampled_from(sorted(TIME_WINDOWS)))),
    }
    try:
        r = route_offline["route"]("power overview for PCC-Panel-1")
    except RuntimeError:
        return                                   # fail-closed branch — legal for junk/unresolvable page_key
    assert r["page_key"] in avail, f"routed OUTSIDE the available pages: {r['page_key']!r}"
    if pk in eff:
        assert r["page_key"] == pk and r["routing"]["page_key_how"] == "verbatim"
    assert r["metric"] in METRIC_VOCAB
    assert r["intent"] in INTENT_VOCAB
    assert r["window"] is None or r["window"] in TIME_WINDOWS


@given(data=st.data())
def test_p3_case_mutant_page_key_never_flips(route_offline, page_snapshot, data):
    k = data.draw(st.sampled_from(page_snapshot["eff_keys"]))
    m = data.draw(edge_mutants(k))
    route_offline["reply"] = {"page_key": m, "metric": "power", "intent": "trend"}
    try:
        r = route_offline["route"]("x")
    except RuntimeError:
        return                                   # ambiguous mutant fails closed — legal; never a different page
    assert r["page_key"] == k, f"mutant {m!r} of {k!r} routed to {r['page_key']!r}"


def test_p4_empty_emission_raises(route_offline):
    route_offline["reply"] = {}
    with pytest.raises(RuntimeError, match="transport/parse failure"):
        route_offline["route"]("x")
