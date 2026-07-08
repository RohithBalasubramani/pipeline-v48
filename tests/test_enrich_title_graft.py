"""TITLE GRAFT [defense-in-depth, metadata-stripping] — a served card must NEVER render NAMELESS: when the payload's
own title leaf is blank (None/''/'—') but cmd_catalog carries the card's title, host/enrich grafts card.title in at the
serve boundary. Chrome-only: an existing title leaf is filled, a real payload title always wins, the payload shape is
never grown, and a reading is never touched. Non-live (pure dict fixtures; _enrich_card offline). [atomic]"""
from __future__ import annotations

from host.enrich import _enrich_card, _graft_card_title


def test_graft_fills_blank_data_title():
    p = {"data": {"title": None, "readings": {"activePower": {"value": 12.5}}}}
    out = _graft_card_title(p, "Power & Energy (Real-Time)")
    assert out["data"]["title"] == "Power & Energy (Real-Time)"


def test_graft_fills_empty_and_dash_titles_too():
    assert _graft_card_title({"data": {"title": ""}}, "T")["data"]["title"] == "T"
    assert _graft_card_title({"data": {"title": "—"}}, "T")["data"]["title"] == "T"


def test_graft_never_clobbers_a_real_payload_title():
    p = {"data": {"title": "Power & Energy"}}
    out = _graft_card_title(p, "Some Catalog Title")
    assert out["data"]["title"] == "Power & Energy"               # the payload's own title wins


def test_graft_root_title_home_when_no_data_dict():
    p = {"title": None, "rows": []}
    out = _graft_card_title(p, "Feeder Overview")
    assert out["title"] == "Feeder Overview"


def test_graft_never_grows_the_payload_shape():
    # no existing title leaf anywhere → nothing is invented (the component's prop shape is the wall)
    p = {"data": {"readings": {}}}
    out = _graft_card_title(p, "T")
    assert "title" not in out and "title" not in out["data"]


def test_graft_no_catalog_title_or_no_payload_is_a_noop():
    p = {"data": {"title": None}}
    assert _graft_card_title(p, None)["data"]["title"] is None    # nothing to graft from (never fabricates)
    assert _graft_card_title(None, "T") is None                   # payload absent → untouched


def test_enrich_card_serves_a_titled_payload():
    # END-TO-END through the FE card build: a completed payload whose data.title an upstream pass stripped to None is
    # served TITLED from cmd_catalog card.title — while the honest-blank readings stay blank (chrome only, no data).
    card = {"card_id": 36, "title": "Power & Energy (Real-Time)", "analytical_story": "s",
            "role_in_story": "r", "slot": "a", "size": "m"}
    completed = {"data": {"title": None,
                          "readings": {"activePower": {"value": None, "unit": "kW", "label": "Active Power"}}}}
    l2 = {"data_instructions": {"asset_name": "DG-1 MFM", "fields": [
        {"slot": "data.readings.activePower.value", "label": "Active Power", "column": "active_power_total_kw"}]},
        "payload": completed, "conforms": True}
    out = _enrich_card(card, "asset-dashboard", {}, l2, completed=completed)
    assert out["payload"]["data"]["title"] == "Power & Energy (Real-Time)"    # never nameless
    assert out["payload"]["data"]["readings"]["activePower"]["value"] in (None, "—")  # data stays honest-blank
