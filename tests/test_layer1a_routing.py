"""Layer 1a — unit + live integration + contract-2 conformance + asset-agnostic + available-pages scope."""
import pytest

from config.available_pages import available_page_keys
from layer1a.db_reads.page_specs import read_page_specs
from layer1a.db_reads.card_titles import read_card_titles
from layer1a.db_reads.cards_intent import read_page_cards
from layer1a.parse.page_key_fallback import resolve_page_key
from layer1a.parse.metric_intent_defaults import clamp_metric_intent
from layer1a.story_builder import _norm_id, build_stories
from layer1a.schema import build_layer1a_output, validate_layer1a_output
from layer1a.route import route
from layer1a.build import run_1a

AVAIL = set(available_page_keys())
RTM = "panel-overview-shell/real-time-monitoring"


def test_page_specs_live():
    specs = read_page_specs()
    assert len(specs) == 68 and all(s["page_key"] for s in specs)  # unfiltered read = all live


def test_card_titles_dict():
    assert len(read_card_titles()) > 30


def test_page_cards_rtm_slot_size():
    cards = read_page_cards(RTM)
    ids = {c["card_id"] for c in cards}
    assert len(cards) == 8 and 5 in ids and 160 in ids
    assert read_page_cards(RTM)[0]["size"]["width_px"]  # real grid size


def test_resolve_page_key():
    keys = ["a/b", "c/d"]
    assert resolve_page_key("a/b", keys) == ("a/b", "verbatim")
    assert resolve_page_key("b", keys) == ("a/b", "segment")     # unique tail segment recovers
    assert resolve_page_key("zzz", keys) == (None, "no_match")   # fail-closed: no silent keys[0] misroute
    assert resolve_page_key(None, keys) == (None, "missing")


def test_clamp_metric_intent():
    assert clamp_metric_intent(None, None) == ("power", "trend")
    assert clamp_metric_intent("Voltage", "SNAPSHOT") == ("voltage", "snapshot")
    assert clamp_metric_intent("power factor", "x") == ("pf", "trend")   # phrase -> canonical keyword
    assert clamp_metric_intent("zzz", "bogus") == ("power", "trend")     # unknown -> default


def test_norm_id():
    assert _norm_id("card 44") == "44" and _norm_id("44") == "44" and _norm_id(44) == "44"


@pytest.mark.live
def test_route_live_in_available():
    r = route("real-time monitoring of PCC-1A panel")
    assert r["page_key"] in AVAIL and "real-time-monitoring" in r["page_key"]
    assert r["metric"] and r["intent"] in {"trend", "distribution", "snapshot", "table", "events"}


@pytest.mark.live
def test_stories_every_card_covered():
    cards = build_stories("real-time monitoring of PCC-1A", RTM, "power", "snapshot")
    assert cards and all(c["analytical_story"].strip() for c in cards)


@pytest.mark.live
def test_e2e_contract2_conformance():
    out = run_1a("real-time monitoring of PCC-1A panel")
    assert validate_layer1a_output(out, AVAIL) == []     # full contract-2 PASS, page is available
    assert out["page_key"] in AVAIL
    assert "interdependency_groups" in out
    c0 = out["cards"][0]
    assert c0["profile"]["card_purpose"] and "fields" in c0["recipe"] and "handling_class" in c0["handling"]


@pytest.mark.live
def test_asset_agnostic_routing():
    a = route("real-time monitoring of PCC-1A panel")["page_key"]
    b = route("real-time monitoring of PCC-2B panel")["page_key"]
    assert a == b
