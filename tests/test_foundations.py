"""Foundations: db_client, llm/client, obs/ai_log, obs/failures — unit + live integration."""
import json
import os

import pytest

from data.db_client import q
from llm import client, config
from obs import ai_log, failures


def test_db_client_basic():
    rows = q("cmd_catalog", "SELECT 1, 'hello'")
    assert rows and rows[0][0] == "1" and rows[0][1] == "hello"


def test_db_client_raises_on_bad_sql():
    with pytest.raises(RuntimeError):
        q("cmd_catalog", "SELECT * FROM no_such_table_xyz_123")


def test_db_client_live_counts_match_canon():
    cards = int(q("cmd_catalog", "SELECT count(*) FROM cards WHERE status='live'")[0][0])
    pages = int(q("cmd_catalog", "SELECT count(*) FROM page_specs WHERE status='live'")[0][0])
    assert cards == 136 and pages == 68  # canon: rebuilt DB (+card 12 promoted scratch→live in the energy-distribution fix)


def test_llm_client_live_returns_dict():
    r = client.call_qwen("You reply ONLY with JSON.", 'Return exactly {"ok": true}. JSON:')
    assert isinstance(r, dict) and r.get("ok") is True


def test_llm_client_fail_open(monkeypatch):
    monkeypatch.setattr(config, "LLM_URL", "http://localhost:1/nope")
    assert client.call_qwen("x", "y", timeout=2) == {}


def test_ai_log_installed_and_logs():
    import urllib.request
    assert urllib.request.urlopen.__name__ == "_logged"  # monkeypatch active
    ai_log.set_run_id("pytest_log")
    client.call_qwen("Reply ONLY JSON.", 'Return {"a":1}. JSON:')
    p = os.path.join(ai_log._OUT, "ai_pytest_log.jsonl")
    assert os.path.exists(p)
    rec = json.loads(open(p).read().strip().splitlines()[-1])
    assert ":8200" in rec["url"] and rec["request"] and rec["response"]


def test_failures_record():
    rec = failures.record("teststage", "boom", card_id=5, run_id="pytest_fail")
    assert rec["stage"] == "teststage" and rec["card_id"] == 5 and rec["reason"] == "boom"
