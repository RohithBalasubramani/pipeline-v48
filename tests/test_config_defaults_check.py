"""tests/test_config_defaults_check.py — configured default keys must resolve to catalog rows (audit 14 F3).

Pins the permanence net for the pcc1a-v1 class of defect: a viewer.default_asset_3d_key with no lt_asset_3d
row silently killed the tier-4 3D fallback for ~189 records. Stubbed catalog (non-live) + one live-lane row
check so the real DB state gates `pytest -m live`."""
from __future__ import annotations

import pytest

import validate.config_defaults_check as CDC


def test_present_row_is_healthy(monkeypatch):
    monkeypatch.setattr("config.viewer_policy.default_asset_3d_key", lambda: "pcc1a-v1")
    import validate.config_defaults_check as m
    monkeypatch.setattr("data.db_client.q", lambda db, sql: [["7"]])
    assert m.check() == []


def test_missing_row_is_a_named_issue(monkeypatch):
    monkeypatch.setattr("config.viewer_policy.default_asset_3d_key", lambda: "pcc1a-v1")
    monkeypatch.setattr("data.db_client.q", lambda db, sql: [])
    issues = CDC.check()
    assert len(issues) == 1 and "pcc1a-v1" in issues[0] and "lt_asset_3d" in issues[0]


def test_no_default_configured_is_honest(monkeypatch):
    monkeypatch.setattr("config.viewer_policy.default_asset_3d_key", lambda: "")
    assert CDC.check() == []


def test_db_outage_skips_silently(monkeypatch):
    monkeypatch.setattr("config.viewer_policy.default_asset_3d_key", lambda: "pcc1a-v1")
    monkeypatch.setattr("data.db_client.q",
                        lambda db, sql: (_ for _ in ()).throw(RuntimeError("connection refused")))
    assert CDC.check() == []                          # never report drift it cannot verify


@pytest.mark.live
def test_live_default_key_resolves():
    """The real DB state: after scripts/seed_pcc1a_asset3d.py the configured default must resolve."""
    issues = CDC.check()
    assert issues == [], issues
