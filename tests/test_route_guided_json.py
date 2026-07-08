"""L1a ROUTING-DETERMINISM — guided_json for the 1a PAGE ROUTER, DEFAULT OFF. [layer1a/route_schema.py,
layer1a/route.py json_schema wiring, db/seed_route_guided_json.sql]

Contract under test (all offline; no HTTP, no DB — app_config reads faked):
  · route_answer_schema() returns None by DEFAULT (absent row / DB down) → call_qwen's json_schema kwarg is inert →
    the router request is BYTE-IDENTICAL to today's json_object path (the flag-off = unchanged fence requirement);
  · flag ON (llm.guided_json.route = 'on'): route_answer_schema() returns the enum-constrained answer schema —
    page_key pinned to THIS prompt's candidate keys, metric/intent pinned to their vocab, all three required;
  · the route stage is INDEPENDENT of the asset_resolve stage (per-call flag; one on must not turn the other on);
  · route.py wires it through json_schema= (flag-gated), NOT the unconditional schema= kwarg — so the request is
    unchanged until the row is flipped, mirroring the 1b asset-resolver seam exactly.
"""
import json
import urllib.request

from llm import client
from layer1a.route_schema import route_answer_schema

_KEYS = ["individual-feeder-meter-shell/energy-power",
         "diesel-generator-asset-dashboard/operations-runtime",
         "transformer-asset-dashboard/thermal-life"]
_METRICS = ["power", "energy", "voltage", "current"]
_INTENTS = ["trend", "distribution", "snapshot", "table", "events"]


def _capture(monkeypatch, cfg_rows=None):
    """Fake the HTTP seam AND config.app_config.cfg (the ONE gate both route_answer_schema and client._cfg read);
    return the list of RAW request payload dicts actually sent."""
    sent = []

    def fake_urlopen(req, timeout=None):
        sent.append(json.loads(req.data.decode()))

        class _R:
            def read(self):
                return json.dumps({"choices": [{"message": {"content": '{"page_key":"x"}'},
                                                "finish_reason": "stop"}]})
        return _R()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    import config.app_config as ac
    rows = cfg_rows or {}
    monkeypatch.setattr(ac, "cfg", lambda k, d: rows.get(k, d))
    return sent


# ── layer1a/route_schema.py: the flag read ──────────────────────────────────────────────────────────────────────────
def test_route_schema_default_off_returns_none(monkeypatch):
    import config.app_config as ac
    monkeypatch.setattr(ac, "cfg", lambda k, d: d)                    # absent row → caller default 'off'
    assert route_answer_schema(_KEYS, _METRICS, _INTENTS) is None


def test_route_schema_on_pins_page_key_enum(monkeypatch):
    import config.app_config as ac
    monkeypatch.setattr(ac, "cfg", lambda k, d: "on" if k == "llm.guided_json.route" else d)
    s = route_answer_schema(_KEYS, _METRICS, _INTENTS)
    assert s is not None
    assert s["properties"]["page_key"]["enum"] == _KEYS               # EXACTLY this prompt's candidates, no drift room
    assert s["properties"]["metric"]["enum"] == _METRICS
    assert s["properties"]["intent"]["enum"] == _INTENTS
    assert s["required"] == ["page_key", "metric", "intent", "window"]
    assert list(s["properties"]) == ["page_key", "metric", "intent", "window"]  # ORDER = taught reply shape in system.md


def test_route_schema_on_includes_window_preset_enum(monkeypatch):
    # route-1a-timewindow: `window` is a 4th REQUIRED enum, DB-driven from config.windows.TIME_WINDOWS + a "none"
    # sentinel. Assert membership (not exact list — the vocab is a tunable DB row) and the pure-string-enum shape.
    import config.app_config as ac
    from config.windows import TIME_WINDOWS
    monkeypatch.setattr(ac, "cfg", lambda k, d: "on" if k == "llm.guided_json.route" else d)
    w = route_answer_schema(_KEYS, _METRICS, _INTENTS)["properties"]["window"]
    assert w["type"] == "string"                                      # xgrammar treats it exactly like metric/intent
    assert "none" in w["enum"]                                        # the no-time sentinel is always present
    assert "last-7-days" in w["enum"]                                 # the acceptance preset is a real TIME_WINDOWS key
    for k in TIME_WINDOWS:                                            # every DB preset is offerable (schema ⊇ vocab)
        assert k in w["enum"]


def test_route_schema_on_is_a_fresh_copy_per_prompt(monkeypatch):
    # the candidate keys are prompt-specific → the schema must reflect the keys PASSED, not a cached constant
    import config.app_config as ac
    monkeypatch.setattr(ac, "cfg", lambda k, d: "on" if k == "llm.guided_json.route" else d)
    other = ["panel-overview-shell/voltage-current"]
    assert route_answer_schema(other, _METRICS, _INTENTS)["properties"]["page_key"]["enum"] == other


# ── llm/client.py wiring at stage='route' ─────────────────────────────────────────────────────────────────────────────
def test_route_flag_off_request_byte_identical(monkeypatch):
    sent = _capture(monkeypatch)                                     # no rows → llm.guided_json.route default 'off'
    client.call_qwen("s", "u", stage="route")
    client.call_qwen("s", "u", stage="route", json_schema={"type": "object"})
    assert len(sent) == 2 and sent[0] == sent[1]                     # kwarg fully inert → byte-identical
    assert sent[1]["response_format"] == {"type": "json_object"}     # legacy default, unchanged


def test_route_flag_on_attaches_json_schema(monkeypatch):
    sent = _capture(monkeypatch, {"llm.guided_json.route": "on"})
    schema = route_answer_schema(_KEYS, _METRICS, _INTENTS)
    client.call_qwen("s", "u", stage="route", json_schema=schema)
    assert sent[0]["response_format"] == {"type": "json_schema", "json_schema": {"name": "out", "schema": schema}}
    assert sent[0]["response_format"]["json_schema"]["schema"]["properties"]["page_key"]["enum"] == _KEYS


def test_route_flag_is_per_stage_independent(monkeypatch):
    # asset_resolve 'on' must NOT turn on guided decoding for the route stage (per-call flag row)
    sent = _capture(monkeypatch, {"llm.guided_json.asset_resolve": "on"})
    client.call_qwen("s", "u", stage="route", json_schema={"type": "object"})
    assert sent[0]["response_format"] == {"type": "json_object"}
