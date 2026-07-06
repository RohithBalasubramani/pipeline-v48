"""Reflect-loop REROUTE-TRIGGER policy [reflect.reroute_on, sweep-#3 r_d7be9457fc]: a page whose emits all CONFORM
with honest-blank gaps + per-leaf reasons is a VALID TERMINAL — the routed page and its cards are KEPT and the reflect
NOTE (user-facing explanation) survives; only HARD emit failures (exception/timeout/non-conforming) re-route. The
legacy honest-gap re-route stays reachable as the DB-tunable 'any_gap' policy. [run/harness _reflect_loop + _preflight_reroute]"""
import pytest

import run.harness as harness


def _cfg(overrides=None):
    vals = {"reflect.reroute_on": "hard_failure", "reflect.min_gap_frac": 0.34, **(overrides or {})}
    return lambda key, default: vals.get(key, default)


def _card(cid, *, conforms=True, gap=False, answerability="full", note=None, failure=None):
    return {"card_id": cid, "conforms": conforms, "gap": gap, "answerability": answerability,
            "data_note": note, "failure": failure, "swap_decision": {"action": "keep"},
            "exact_metadata": {"variant": "x"}, "data_instructions": {"consumer": {"endpoint": "e"}}}


def _out(page="ups-asset-dashboard/source-transfer"):
    return {"layer1a": {"page_key": page,
                        "cards": [{"card_id": 54, "title": "Transfer Readiness"},
                                  {"card_id": 55, "title": "Transfer Activity"},
                                  {"card_id": 56, "title": "Composite Score"}]},
            "layer1b": {"asset": {"name": "GIC-01-N3-UPS-01"}, "column_basket": {"columns": []}},
            "validation": None, "layer2": None, "notes": {"loop1": [], "loop2": None}, "errors": {}}


def _no_reroute_1a(*a, **k):
    raise AssertionError("run_1a must NOT be called — honest-blank is a valid terminal, not a re-route trigger")


# ---------------------------------------------------------------- honest terminal (the r_d7be9457fc regression)

def test_conforming_honest_blank_page_does_not_reroute(monkeypatch):
    """Cards 54/55 = CONFORMING answerability='none' with reasons (the proper output for unmeasured transfer
    telemetry) → the page stays as routed, all cards kept, loop2 carries the user-facing note, NO re-route."""
    l2 = {54: _card(54, gap=True, answerability="none", note="transfer telemetry is not measured on this UPS meter"),
          55: _card(55, gap=True, answerability="none", note="transfer counts are not electrical measurements"),
          56: _card(56, answerability="partial", note="total power as proxy")}
    calls = []
    monkeypatch.setattr(harness, "run_2_all", lambda rid, l1a, l1b: calls.append(rid) or l2)
    monkeypatch.setattr(harness, "run_1a", _no_reroute_1a)
    monkeypatch.setattr(harness, "cfg", _cfg())
    out = _out()
    harness._reflect_loop(out, "ups source transfer for GIC-01-N3-UPS-01", "cmd_catalog", "r_test_honest")
    assert len(calls) == 1                                            # ONE Layer-2 pass; no burned re-emit
    assert out["layer1a"]["page_key"] == "ups-asset-dashboard/source-transfer"   # routed page KEPT
    assert out["layer2"] is l2 and set(out["layer2"]) == {54, 55, 56}            # cards KEPT
    assert out["errors"] == {}
    note = out["notes"]["loop2"]                                      # the reflect NOTE survives (explanation, not discard)
    assert note and "honest-blank" in note and "Transfer Readiness" in note
    assert "not measured" in note


def test_honest_blank_keeps_loop1_per_card_notes(monkeypatch):
    l2 = {54: _card(54, gap=True, answerability="none", note="unmeasured quantity")}
    monkeypatch.setattr(harness, "run_2_all", lambda rid, l1a, l1b: l2)
    monkeypatch.setattr(harness, "run_1a", _no_reroute_1a)
    monkeypatch.setattr(harness, "cfg", _cfg())
    out = _out()
    harness._reflect_loop(out, "p", "cmd_catalog", "r_test_notes")
    assert out["notes"]["loop1"] == [{"card_id": 54, "title": "Transfer Readiness",
                                      "answerability": "none", "note": "unmeasured quantity"}]


# ---------------------------------------------------------------- hard failures still re-route/re-loop

def test_hard_failed_emits_still_reroute(monkeypatch):
    """conforms=False (emit exception / LLM timeout / non-conforming envelope) over the fraction threshold →
    the re-route fires exactly as before: feedback to 1a, failed page mechanically excluded, Layer 2 re-run."""
    bad = {54: _card(54, conforms=False, answerability="partial",
                     failure={"stage": "llm", "reason": "llm_timeout", "detail": "llm_timeout"}),
           55: {"card_id": 55, "exception": "RuntimeError: emit blew up", "conforms": False,
                "exact_metadata": None, "payload": None, "swap_decision": {"action": "keep"}},
           56: _card(56)}
    good = {60: _card(60), 61: _card(61)}
    emits, reroutes = [], []

    def fake_2_all(rid, l1a, l1b):
        emits.append(l1a["page_key"])
        return bad if len(emits) == 1 else good

    def fake_1a(prompt, db, feedback=None, exclude_page_key=None):
        reroutes.append({"feedback": feedback, "exclude": exclude_page_key})
        return {"page_key": "ups-asset-dashboard/output-load-capacity",
                "cards": [{"card_id": 60, "title": "A"}, {"card_id": 61, "title": "B"}]}

    monkeypatch.setattr(harness, "run_2_all", fake_2_all)
    monkeypatch.setattr(harness, "run_1a", fake_1a)
    monkeypatch.setattr(harness, "_validate", lambda out, db, rid: None)
    monkeypatch.setattr(harness, "cfg", _cfg())
    out = _out()
    harness._reflect_loop(out, "p", "cmd_catalog", "r_test_hard")
    assert len(reroutes) == 1                                          # the re-route DID fire
    assert reroutes[0]["exclude"] == "ups-asset-dashboard/source-transfer"
    assert "llm_timeout" in reroutes[0]["feedback"]                    # feedback built from the HARD failures
    assert out["layer1a"]["page_key"] == "ups-asset-dashboard/output-load-capacity"
    assert out["layer2"] is good and emits == ["ups-asset-dashboard/source-transfer",
                                               "ups-asset-dashboard/output-load-capacity"]


def test_single_hard_fail_below_frac_stays(monkeypatch):
    """The min_gap_frac gate still guards the hard-failure trigger: 1-of-6 must not discard a healthy page."""
    l2 = {i: _card(i) for i in range(1, 6)}
    l2[6] = _card(6, conforms=False, failure={"stage": "emit", "reason": "bad envelope", "detail": "x"})
    monkeypatch.setattr(harness, "run_2_all", lambda rid, l1a, l1b: l2)
    monkeypatch.setattr(harness, "run_1a", _no_reroute_1a)
    monkeypatch.setattr(harness, "cfg", _cfg())
    out = _out()
    harness._reflect_loop(out, "p", "cmd_catalog", "r_test_frac")
    assert out["layer1a"]["page_key"] == "ups-asset-dashboard/source-transfer"
    assert "NOT re-routed" in out["notes"]["loop2"]


# ---------------------------------------------------------------- DB-tunable rollback + no_data unchanged

def test_any_gap_policy_restores_legacy_gap_reroute(monkeypatch):
    """reflect.reroute_on='any_gap' (a cmd_catalog app_config edit, no code change) re-enables the old behavior."""
    bad = {54: _card(54, gap=True, answerability="none", note="unmeasured"),
           55: _card(55, gap=True, answerability="none", note="unmeasured"),
           56: _card(56)}
    reroutes = []

    def fake_1a(prompt, db, feedback=None, exclude_page_key=None):
        reroutes.append(exclude_page_key)
        return {"page_key": "other-page", "cards": [{"card_id": 60, "title": "A"}]}

    seen = []
    monkeypatch.setattr(harness, "run_2_all", lambda rid, l1a, l1b: seen.append(1) or (bad if len(seen) == 1 else {60: _card(60)}))
    monkeypatch.setattr(harness, "run_1a", fake_1a)
    monkeypatch.setattr(harness, "_validate", lambda out, db, rid: None)
    monkeypatch.setattr(harness, "cfg", _cfg({"reflect.reroute_on": "any_gap"}))
    out = _out()
    harness._reflect_loop(out, "p", "cmd_catalog", "r_test_legacy")
    assert reroutes == ["ups-asset-dashboard/source-transfer"] and out["layer1a"]["page_key"] == "other-page"


def test_no_data_asset_never_reroutes_even_on_hard_fail(monkeypatch):
    l2 = {54: _card(54, conforms=False, gap=True, answerability="none",
                    failure={"stage": "emit", "reason": "x", "detail": "x"})}
    monkeypatch.setattr(harness, "run_2_all", lambda rid, l1a, l1b: l2)
    monkeypatch.setattr(harness, "run_1a", _no_reroute_1a)
    monkeypatch.setattr(harness, "cfg", _cfg())
    out = _out()
    harness._reflect_loop(out, "p", "cmd_catalog", "r_test_nodata", no_reroute=True)
    assert "no logged data" in out["notes"]["loop2"]
    assert out["layer1a"]["page_key"] == "ups-asset-dashboard/source-transfer"


# ---------------------------------------------------------------- pre-L2 expected-gap re-route obeys the same policy

def test_preflight_expected_gaps_are_honest_terminal_by_default(monkeypatch):
    """validation expected-gaps are HONEST gaps (unmeasured topology), never hard failures — under the default
    policy the routed page is kept (cards honest-blank per-leaf via the emit's feasibility note), no pre-emit discard."""
    monkeypatch.setattr(harness, "run_1a", _no_reroute_1a)
    monkeypatch.setattr(harness, "cfg", _cfg())
    out = _out()
    out["validation"] = {"expected_gap_frac": 0.67,
                         "expected_gaps": [{"card_id": 54, "title": "Transfer Readiness", "reason": "no feeders"},
                                           {"card_id": 55, "title": "Transfer Activity", "reason": "no feeders"}]}
    harness._preflight_reroute(out, "p", "cmd_catalog", "r_test_pre")
    assert out["layer1a"]["page_key"] == "ups-asset-dashboard/source-transfer"
    assert out["errors"] == {}


def test_preflight_reroutes_under_any_gap_policy(monkeypatch):
    reroutes = []

    def fake_1a(prompt, db, feedback=None, exclude_page_key=None):
        reroutes.append(exclude_page_key)
        return {"page_key": "other-page", "cards": []}

    monkeypatch.setattr(harness, "run_1a", fake_1a)
    monkeypatch.setattr(harness, "_validate", lambda out, db, rid: None)
    monkeypatch.setattr(harness, "cfg", _cfg({"reflect.reroute_on": "any_gap"}))
    out = _out()
    out["validation"] = {"expected_gap_frac": 0.67,
                         "expected_gaps": [{"card_id": 54, "title": "T", "reason": "no feeders"},
                                           {"card_id": 55, "title": "U", "reason": "no feeders"}]}
    harness._preflight_reroute(out, "p", "cmd_catalog", "r_test_pre2")
    assert reroutes == ["ups-asset-dashboard/source-transfer"] and out["layer1a"]["page_key"] == "other-page"


# ---------------------------------------------------------------- the shipped default row matches the code default

def test_db_row_if_present_is_hard_failure():
    """The seeded cmd_catalog row must agree with the code default (db/seed_reflect_reroute_policy.sql). Skips
    offline — the code default already gives the same behavior (cfg fail-open)."""
    from data.db_client import q
    from config.databases import CMD_CATALOG
    try:
        rows = q(CMD_CATALOG, "SELECT value FROM app_config WHERE key = 'reflect.reroute_on'")
    except Exception:
        pytest.skip("cmd_catalog unreachable — cfg falls back to the identical code default")
    if not rows:
        pytest.skip("row not seeded — cfg falls back to the identical code default")
    assert rows[0][0] == "hard_failure"
