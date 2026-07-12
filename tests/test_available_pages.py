"""config/available_pages.py — the add/remove provision."""
import pytest

from config.available_pages import AVAILABLE_PAGES, available_page_keys, filter_to_available
from layer1a.route import route


def test_available_pages_set():
    # 9 EMS pages (5 panel-overview + 4 equipment-detail) + 9 asset deep-tab pages = 18 routable page_keys.
    assert len(AVAILABLE_PAGES) == 18
    assert "panel-overview-shell/real-time-monitoring" in AVAILABLE_PAGES
    assert "ups-asset-dashboard/output-load-capacity" in AVAILABLE_PAGES


def test_filter_to_available():
    specs = [{"page_key": "panel-overview-shell/real-time-monitoring"}, {"page_key": "zzz/not-available"}]
    assert [s["page_key"] for s in filter_to_available(specs)] == ["panel-overview-shell/real-time-monitoring"]


def test_env_override(monkeypatch):
    monkeypatch.setenv("V48_AVAILABLE_PAGES", "x/one, y/two")
    assert available_page_keys() == ["x/one", "y/two"]


@pytest.mark.live
def test_route_stays_in_available():
    allow = set(available_page_keys())
    for p in ["UPS battery health", "transformer thermal life", "voltage current health"]:
        assert route(p)["page_key"] in allow  # off-catalog prompts pulled to nearest available
