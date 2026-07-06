"""TRUNCATION FAIL-FAST + PROMPT-BUDGET PREFLIGHT [backlog A3 — llm/client.py, ai_r_f9787f915f]: a
finish_reason=length reply is DETERMINISTIC for a pinned-seed temp-0 call, so it must (a) never ship even when the
truncated JSON happens to be balanced, (b) never be retried by the parse-retry loop (llm.no_retry_kinds, the same
row layer2/emit/emit.py honors), and (c) an over-window prompt must be caught by the (system+user)//4 preflight
(llm.prompt_budget_tok) and never sent at all. All non-live, deterministic — the HTTP seam is faked."""
import json
import urllib.request

import pytest

from llm import client


class _Resp:
    """Minimal file-like body for json.load()."""

    def __init__(self, content, finish):
        self._body = json.dumps({"choices": [{"message": {"content": content}, "finish_reason": finish}]})

    def read(self):
        return self._body


def _wire(monkeypatch, replies, cfg=None):
    """Fake the HTTP seam: serve one (content, finish_reason) per call (last one repeats); return the list of USER
    messages actually sent so a test can assert call count + retry-prompt growth. `cfg` overrides client._cfg rows."""
    sent = []

    def fake_urlopen(req, timeout=None):
        sent.append(json.loads(req.data.decode())["messages"][1]["content"])
        content, finish = replies[min(len(sent) - 1, len(replies) - 1)]
        return _Resp(content, finish)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    rows = cfg or {}
    monkeypatch.setattr(client, "_cfg", lambda k, d: rows.get(k, d))
    return sent


def test_truncated_balanced_json_fails_fast_and_never_ships(monkeypatch):
    # finish=length with a BALANCED reply: the old code returned it as success; a nested object can close early and
    # still parse, so it must classify 'truncated' BEFORE the parse-success return — and never retry (1 call only).
    sent = _wire(monkeypatch, [('{"a": 1}', "length")])
    out = client.call_qwen("sys", "user", on_error="marker")
    assert out.get("_llm_error") == "truncated"
    assert "finish_reason=length" in out.get("_llm_error_detail", "")
    assert len(sent) == 1                                          # deterministic failure → no parse-retry


def test_truncated_fail_closed_raises_with_kind(monkeypatch):
    sent = _wire(monkeypatch, [('{"a": 1}', "length")])
    with pytest.raises(client.LlmError) as ei:
        client.call_qwen("sys", "user", on_error="raise")
    assert ei.value.kind == "truncated" and len(sent) == 1


def test_parse_failure_still_retries_once_and_recovers(monkeypatch):
    # Non-deterministic-looking failures (garbled reply) keep their ONE bounded retry with the error appended.
    sent = _wire(monkeypatch, [("not json at all", "stop"), ('{"ok": true}', "stop")])
    out = client.call_qwen("sys", "user", on_error="marker")
    assert out == {"ok": True} and len(sent) == 2
    assert "NOT USABLE" in sent[1]                                 # retry prompt carries the parse feedback


def test_persistent_no_json_exhausts_the_single_retry(monkeypatch):
    sent = _wire(monkeypatch, [("still not json", "stop")])
    out = client.call_qwen("sys", "user", on_error="marker")
    assert out.get("_llm_error") == "no_json" and len(sent) == 2


def test_no_retry_kinds_row_extends_the_fail_fast_set(monkeypatch):
    # config-first: editing the llm.no_retry_kinds row changes behavior with no code change.
    sent = _wire(monkeypatch, [("still not json", "stop")], cfg={"llm.no_retry_kinds": "timeout,truncated,no_json"})
    out = client.call_qwen("sys", "user", on_error="marker")
    assert out.get("_llm_error") == "no_json" and len(sent) == 1


def test_over_budget_preflight_never_sends_the_call(monkeypatch):
    sent = _wire(monkeypatch, [('{"a": 1}', "stop")], cfg={"llm.prompt_budget_tok": 10})
    out = client.call_qwen("s", "u" * 200, on_error="marker")      # ≈50 tok > 10-tok budget
    assert out.get("_llm_error") == "over_budget"
    assert "llm.prompt_budget_tok=10" in out.get("_llm_error_detail", "")
    assert sent == []                                              # the doomed call was never sent


def test_over_budget_counts_system_plus_user(monkeypatch):
    # The budget must count system+user (the emit char budget counts user-only — that gap is the A3(c) evidence).
    sent = _wire(monkeypatch, [('{"a": 1}', "stop")], cfg={"llm.prompt_budget_tok": 40})
    out = client.call_qwen("s" * 400, "u", on_error="marker")      # system alone ≈100 tok > 40
    assert out.get("_llm_error") == "over_budget" and sent == []


def test_budget_zero_disables_the_preflight(monkeypatch):
    sent = _wire(monkeypatch, [('{"a": 1}', "stop")], cfg={"llm.prompt_budget_tok": 0})
    assert client.call_qwen("s" * 4000, "u" * 400000) == {"a": 1} and len(sent) == 1


def test_grown_retry_prompt_over_budget_skips_the_doomed_retry(monkeypatch):
    # Initial prompt fits (≈100 tok ≤ 105) but the retry APPENDS the error text (the ptok 46,438→46,589 growth) —
    # the grown retry crosses the budget, so it is skipped and the REAL failure kind is kept, annotated.
    sent = _wire(monkeypatch, [("not json", "stop")], cfg={"llm.prompt_budget_tok": 105})
    out = client.call_qwen("s" * 40, "u" * 360, on_error="marker")
    assert out.get("_llm_error") == "no_json" and len(sent) == 1
    assert "parse-retry skipped" in out.get("_llm_error_detail", "")


def test_over_budget_default_on_error_is_fail_open_empty(monkeypatch):
    sent = _wire(monkeypatch, [('{"a": 1}', "stop")], cfg={"llm.prompt_budget_tok": 10})
    assert client.call_qwen("s", "u" * 200) == {} and sent == []   # legacy fail-open contract unchanged
