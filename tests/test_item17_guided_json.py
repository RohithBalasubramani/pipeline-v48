"""ITEM 17 stage 1 — guided_json for the 1b asset resolver, DEFAULT OFF. [llm/client.py json_schema kwarg,
layer1b/resolve/answer_schema.py, db/seed_item17_guided_json.sql]

Contract under test (all non-live; the HTTP seam and app_config reads are faked):
  · flag OFF (default / absent row / no stage): call_qwen(..., json_schema=...) builds a request payload
    BYTE-IDENTICAL to a call without the kwarg — response_format stays {"type":"json_object"};
  · flag ON (llm.guided_json.<stage> = 'on'): the payload carries response_format json_schema with the given schema
    (the param probed live on :8200 vLLM 0.16.1 — the legacy `guided_json` extra-body param is ignored there);
  · the pre-existing unconditional `schema` kwarg is untouched, and always wins over json_schema;
  · asset_answer_schema() returns None by default and the {names,confident,candidates} schema when the row is on;
  · resolve_asset passes the flag-driven kwarg through to call_qwen (None on the default path)."""
import json
import urllib.request

from unittest.mock import patch

from llm import client
from layer1b.resolve.answer_schema import ASSET_ANSWER_SCHEMA, asset_answer_schema
from layer1b.resolve import asset_resolve as ar

_SCHEMA = {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"]}


def _capture(monkeypatch, cfg_rows=None):
    """Fake the HTTP seam; return the list of RAW request payload dicts actually sent."""
    sent = []

    class _Resp:
        def read(self):
            return json.dumps({"choices": [{"message": {"content": '{"ok": 1}'}, "finish_reason": "stop"}]})

    def fake_urlopen(req, timeout=None):
        sent.append(json.loads(req.data.decode()))
        return _Resp()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    rows = cfg_rows or {}
    monkeypatch.setattr(client, "_cfg", lambda k, d: rows.get(k, d))
    return sent


# ── llm/client.py: json_schema kwarg, flag-gated ────────────────────────────────────────────────────────────────────
def test_flag_off_json_schema_kwarg_is_byte_identical(monkeypatch):
    sent = _capture(monkeypatch)                                     # no rows → llm.guided_json.* default 'off'
    assert client.call_qwen("s", "u", stage="asset_resolve") == {"ok": 1}
    assert client.call_qwen("s", "u", stage="asset_resolve", json_schema=_SCHEMA) == {"ok": 1}
    assert len(sent) == 2 and sent[0] == sent[1]                     # BYTE-identical payload, kwarg fully inert
    assert sent[1]["response_format"] == {"type": "json_object"}     # legacy default response_format


def test_flag_off_kwarg_absent_request_unchanged(monkeypatch):
    sent = _capture(monkeypatch)
    client.call_qwen("s", "u", stage="asset_resolve")
    assert sent[0]["response_format"] == {"type": "json_object"} and "json_schema" not in json.dumps(sent[0])


def test_flag_on_attaches_response_format_json_schema(monkeypatch):
    sent = _capture(monkeypatch, {"llm.guided_json.asset_resolve": "on"})
    out = client.call_qwen("s", "u", stage="asset_resolve", json_schema=_SCHEMA)
    assert out == {"ok": 1}
    assert sent[0]["response_format"] == {"type": "json_schema", "json_schema": {"name": "out", "schema": _SCHEMA}}


def test_flag_on_other_stage_stays_off(monkeypatch):
    # the row is PER-CALL (per stage): asset_resolve 'on' must not leak guided decoding into any other stage
    sent = _capture(monkeypatch, {"llm.guided_json.asset_resolve": "on"})
    client.call_qwen("s", "u", stage="basket", json_schema=_SCHEMA)
    client.call_qwen("s", "u", json_schema=_SCHEMA)                  # no stage at all → off
    assert all(p["response_format"] == {"type": "json_object"} for p in sent)


def test_explicit_schema_kwarg_contract_untouched(monkeypatch):
    # pre-item-17 `schema` stays UNCONDITIONAL (no flag), and wins over json_schema when both are passed
    sent = _capture(monkeypatch, {"llm.guided_json.asset_resolve": "on"})
    other = {"type": "object", "properties": {"b": {"type": "integer"}}}
    client.call_qwen("s", "u", schema=other)                                          # no flag row needed
    client.call_qwen("s", "u", stage="asset_resolve", schema=other, json_schema=_SCHEMA)
    assert all(p["response_format"]["json_schema"]["schema"] == other for p in sent)


# ── layer1b/resolve/answer_schema.py: the flag read ─────────────────────────────────────────────────────────────────
def test_answer_schema_default_off_returns_none(monkeypatch):
    import config.app_config as ac
    monkeypatch.setattr(ac, "cfg", lambda k, d: d)                   # absent row → caller default 'off'
    assert asset_answer_schema() is None


def test_answer_schema_on_returns_resolver_contract(monkeypatch):
    import config.app_config as ac
    monkeypatch.setattr(ac, "cfg", lambda k, d: "on" if k == "llm.guided_json.asset_resolve" else d)
    s = asset_answer_schema()
    assert s is ASSET_ANSWER_SCHEMA
    assert set(s["properties"]) == {"names", "confident", "candidates"}      # candidates kept: ambiguous branch
    # ONLY confident required: forcing `names` first biased the grammar into the pin shape and flipped a live
    # ambiguous decision ('spare feeder' control replay) — the prompt's ambiguous contract has NO names key.
    assert s["required"] == ["confident"]
    assert list(s["properties"]) == ["names", "confident", "candidates"]     # property ORDER = the taught shapes
    assert s["properties"]["names"] == {"type": "array", "items": {"type": "string"}}
    assert s["properties"]["confident"] == {"type": "boolean"}


# ── layer1b/resolve/asset_resolve.py: the call-site pass-through ────────────────────────────────────────────────────
_ROWS = [
    [1, "Alpha Meter", "gic_alpha", "", "LG-1", "AHU", True, False, False, True],
    [2, "Beta Meter", "gic_beta", "", "LG-1", "AHU", True, False, False, True],
]


class _Recorder:
    def __init__(self, result):
        self.calls, self._result = [], result

    def __call__(self, system, user, **kw):
        self.calls.append(kw)
        return self._result


def _run_resolve(rec):
    with patch.object(ar, "asset_candidates", return_value=[list(r) for r in _ROWS]), \
         patch.object(ar, "class_from_subject", return_value=None), \
         patch.object(ar, "call_qwen", rec):
        return ar.resolve_asset("health check for the alpha meter")


def test_resolve_asset_passes_none_when_flag_off():
    rec = _Recorder({"confident": True, "names": ["Alpha Meter"], "candidates": []})
    with patch.object(ar, "asset_answer_schema", return_value=None):           # default path
        r = _run_resolve(rec)
    assert r["how"] == "AI" and r["asset"]["mfm_id"] == 1                      # decision unchanged
    assert rec.calls and all(c.get("json_schema") is None for c in rec.calls)  # kwarg carried, but inert
    assert all(c.get("stage") == "asset_resolve" for c in rec.calls)


def test_resolve_asset_passes_schema_when_flag_on():
    rec = _Recorder({"confident": True, "names": ["Alpha Meter"], "candidates": []})
    with patch.object(ar, "asset_answer_schema", return_value=ASSET_ANSWER_SCHEMA):
        r = _run_resolve(rec)
    assert r["how"] == "AI" and r["asset"]["mfm_id"] == 1
    assert all(c.get("json_schema") is ASSET_ANSWER_SCHEMA for c in rec.calls)
