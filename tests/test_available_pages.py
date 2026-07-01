"""config/available_pages.py — the add/remove provision."""
from config.available_pages import AVAILABLE_PAGES, available_page_keys, filter_to_available
from layer1a.route import route


def test_nine_available():
    assert len(AVAILABLE_PAGES) == 9
    assert "panel-overview-shell/real-time-monitoring" in AVAILABLE_PAGES


def test_filter_to_available():
    specs = [{"page_key": "panel-overview-shell/real-time-monitoring"}, {"page_key": "zzz/not-available"}]
    assert [s["page_key"] for s in filter_to_available(specs)] == ["panel-overview-shell/real-time-monitoring"]


def test_env_override(monkeypatch):
    monkeypatch.setenv("V48_AVAILABLE_PAGES", "x/one, y/two")
    assert available_page_keys() == ["x/one", "y/two"]


def test_route_stays_in_available():
    allow = set(available_page_keys())
    for p in ["UPS battery health", "transformer thermal life", "voltage current health"]:
        assert route(p)["page_key"] in allow  # off-catalog prompts pulled to nearest available
