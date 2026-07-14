"""tests/test_reconcile_no_mirror_telemetry.py — T0-3: the granularity-reconcile harness step must not swallow a REAL
granularity mismatch silently when NO mirror page exists. run/reconcile_granularity.apply()'s `if not mirror` branch
used to `return out` with zero telemetry, so a single-meter asset stuck on a panel-aggregate shell (with no
correct-granularity mirror page available) left no stage record and no failure. It now records BOTH
stage(..., skipped='no_mirror', ...) AND obs.failures.record('granularity_reconcile', 'no_mirror', ...), while the
decision path stays byte-identical (still `return out`, no re-route).

Offline / hermetic: obs.stage + obs.failures + the page-spec readers + run_1a_to are ALL monkeypatched on the module's
OWN bindings (run.reconcile_granularity imports them by name, so patching the source modules would miss). No live DB,
no LLM."""
import copy

import run.reconcile_granularity as rg


# ── canned fixtures (page_specs rows carry page_key + shell; shell labels verbatim from page_specs) ─────────────────
_PANEL_PAGE = {"page_key": "panel-overview-shell/real-time-monitoring", "shell": "Panel overview shell"}
_METER_PAGE = {"page_key": "individual-feeder-meter-shell/real-time-monitoring",
               "shell": "Individual feeder / meter shell"}


def _out(asset, page=_PANEL_PAGE):
    return {
        "layer1a": {"page_key": page["page_key"], "shell": page["shell"], "metric": "power", "intent": "snapshot"},
        "layer1b": {"asset": dict(asset)},
        "notes": {},
    }


def _patch_common(monkeypatch, specs, staged, failures):
    """Patch the step's module-local bindings: stage/record_failure capture lists + deterministic page-spec readers."""
    monkeypatch.setattr(rg, "stage", lambda run_id, name, **f: staged.append((run_id, name, f)))
    monkeypatch.setattr(rg, "record_failure", lambda *a, **k: failures.append((a, k)))
    monkeypatch.setattr(rg, "read_page_specs", lambda db: [dict(s) for s in specs])
    monkeypatch.setattr(rg, "filter_to_available", lambda s: s)      # allow-list pass-through (no cfg/DB read)
    monkeypatch.setattr(rg, "run_1a_to", _boom)                      # default: the reroute path must NOT fire


def _boom(*a, **k):
    raise AssertionError("run_1a_to must not be called on this path")


# ── (a) REAL mismatch + NO mirror page => ONE skipped='no_mirror' record + ONE failure record ───────────────────────
def test_no_mirror_records_skipped_telemetry(monkeypatch):
    staged, failures = [], []
    # only the routed panel page exists — the meter-shell mirror is absent from the live specs
    _patch_common(monkeypatch, [_PANEL_PAGE], staged, failures)
    out = _out({"name": "GIC-01-N3-UPS-01", "has_feeders": False, "class": "UPS"})
    before = copy.deepcopy(out)

    got = rg.apply(out, "real time monitoring for GIC-01-N3-UPS-01", "cmd_catalog", "rid-a")

    assert got is out and got == before                              # decision path untouched: same object, unmutated
    assert len(staged) == 1
    run_id, name, f = staged[0]
    assert (run_id, name) == ("rid-a", "granularity_reconcile")
    assert f.get("skipped") == "no_mirror"
    assert f.get("was") == _PANEL_PAGE["page_key"]
    assert f.get("shell") == _PANEL_PAGE["shell"]
    assert f.get("want") == "meter"                                  # the correct-granularity group it wanted
    assert f.get("has_feeders") is False
    # the failure recorder fires too (stage()'s fan-out ignores skipped=, so the module records it explicitly)
    assert len(failures) == 1
    fa, fk = failures[0]
    assert fa[:2] == ("granularity_reconcile", "no_mirror")
    assert fk.get("run_id") == "rid-a"
    assert "no mirror page" in fk.get("detail", "")


# ── (b) no mismatch => NO record (matching granularity + undecidable asset both stay silent) ────────────────────────
def test_no_mismatch_records_nothing(monkeypatch):
    staged, failures = [], []
    _patch_common(monkeypatch, [_PANEL_PAGE], staged, failures)
    # an aggregate Panel on the panel shell = correct granularity — nothing to reconcile, nothing to record
    rg.apply(_out({"name": "PCC-1A", "has_feeders": True, "class": "Panel"}),
             "panel overview for PCC-1A", "cmd_catalog", "rid-b")
    assert staged == [] and failures == []


def test_undecidable_asset_records_nothing(monkeypatch):
    staged, failures = [], []
    _patch_common(monkeypatch, [_PANEL_PAGE], staged, failures)
    # has_feeders=None AND no class = undecidable — the reconcile never fires, so no_mirror must not be claimed
    rg.apply(_out({"name": "Mystery", "has_feeders": None, "class": None}),
             "real time monitoring for Mystery", "cmd_catalog", "rid-u")
    assert staged == [] and failures == []


# ── (c) mirror EXISTS => the existing reroute path fires, unchanged (no skipped record) ─────────────────────────────
def test_mirror_present_reroutes_as_before(monkeypatch):
    staged, failures = [], []
    _patch_common(monkeypatch, [_PANEL_PAGE, _METER_PAGE], staged, failures)
    calls = []

    def fake_run_1a_to(prompt, page_key, metric, intent, db, *, reason=None):
        calls.append({"page_key": page_key, "metric": metric, "intent": intent, "reason": reason})
        return {"page_key": page_key, "shell": _METER_PAGE["shell"], "metric": metric, "intent": intent,
                "cards": [{"card_id": 1}, {"card_id": 2}]}

    monkeypatch.setattr(rg, "run_1a_to", fake_run_1a_to)
    out = _out({"name": "GIC-01-N3-UPS-01", "has_feeders": False, "class": "UPS"})

    got = rg.apply(out, "real time monitoring for GIC-01-N3-UPS-01", "cmd_catalog", "rid-c")

    assert len(calls) == 1 and calls[0]["page_key"] == _METER_PAGE["page_key"]
    assert got["layer1a"]["page_key"] == _METER_PAGE["page_key"]     # 1a rebuilt onto the mirror
    assert "reconcile" in got["notes"]
    assert len(staged) == 1
    run_id, name, f = staged[0]
    assert (run_id, name) == ("rid-c", "granularity_reconcile")
    assert f.get("was") == _PANEL_PAGE["page_key"] and f.get("now") == _METER_PAGE["page_key"]
    assert "skipped" not in f                                        # the success record, not the no_mirror record
    assert f.get("cards") == 2
    assert failures == []                                            # a successful reconcile is not a failure
