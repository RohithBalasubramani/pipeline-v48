"""tools/guard_corpus_replay.py — GUARD CORPUS-REPLAY HARNESS (deterministic cert anchor for fab_guards).

The sibling of tools/wall_corpus_replay.py — but where THAT tool replays the Layer-2 honest-blank GATES against archived
emit traffic, this one pins the POST-FILL FABRICATION GUARDS (ems_exec/executor/fab_guards/) against a committed
baseline so every future guard edit is regression-gated. The guards had ZERO coverage in the 0-fabrication cert
(wall_corpus_replay never touches them; the sweep judge keys only on payload_error) — this closes that gap.

It carries a small self-contained CORPUS of representative guard-input fixtures — one per fabrication CLASS the guards
kill — and replays each through the CURRENT fab_guards.apply(), recording the exact gap (cause, slot) tuples produced.
No live DB: the mockable neuract reads (column_logged / latest_ts / present_columns), the nameplate slot map, the
derivation-binding resolver and the reason-template renderer are stubbed with unittest.mock so the replay is fully
deterministic offline, and every DB KNOB is driven through a config.app_config.cfg stub (never the live app_config).

    PYTHONPATH=. python3 tools/guard_corpus_replay.py --baseline    # write outputs/guard_replay_baseline.json (commit)
    PYTHONPATH=. python3 tools/guard_corpus_replay.py               # REPLAY + diff vs the committed baseline

Default run exit codes: 0 = byte-identical to the committed baseline; 1 = DRIFT (any new / dropped / changed gap, or a
changed out_mutated flag, in a fixture OR in the per-CLASS knob matrix) — it prints the per-fixture delta. This is the
cert anchor: run it before AND after any guard change; a new blank must be a real fabrication, a vanished blank must be
an intended release, and the knob matrix must not shift its semantics.

Corpus classes covered (see CORPUS): CLASS 1 epoch scalar+array + time-axis-exempt; CLASS 2 null-column (+ present-
logged exempt + DB-outage conclusiveness gate); CLASS 3 no-source numeric; live-literal string (+ nameplate-rating
exempt); CLASS 4 legendValue seed blank + structural chrome survives + raw==stripped metadata kept; writer-aware CLASS 2
(agg_row_present skips); roster-slot exemption.

The per-CLASS KNOB MATRIX additionally re-runs the whole corpus with each guard valve (fab_guards.<name>) flipped OFF and
with fab_guards.mode=report, recording the fixture outcomes, so a knob-semantics regression (a valve that stops gating,
a report mode that starts mutating) is caught too.
"""
import argparse
import contextlib
import copy
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
# `layer2`/`ems_exec` also exist one level up (backend/) — pin THIS pipeline's packages (conftest/wall-replay pattern).
for _m in [m for m in list(sys.modules) if m.split(".")[0] in ("layer2", "ems_exec", "config")]:
    _f = getattr(sys.modules[_m], "__file__", "") or ""
    if _f and not os.path.abspath(_f).startswith(ROOT):
        del sys.modules[_m]

from ems_exec.executor import fab_guards as G          # noqa: E402  (the guard under test — read-only use)

_BASELINE = os.path.join(ROOT, "outputs", "guard_replay_baseline.json")
_EPOCH, _EPOCH2 = 1783362600000, 1783362700000        # ~2026 in epoch ms; both >= the 1e12 fabrication floor


# ── the corpus ────────────────────────────────────────────────────────────────────────────────────────────────────
def _card73_default():
    """The card-53/73 ScoreHistoryCard default: per-series scalar legendValue 52/71/85/43 (the audit's fabricated
    legend readings) beside structural chrome (key/color/dashed/label) + empty values arrays."""
    return {"backupHistory": {"series": [
        {"key": "index",        "color": "#444443", "dashed": False, "label": "Autonomy index",     "legendValue": 52, "values": []},
        {"key": "runtimeScore", "color": "#86a86b", "dashed": False, "label": "Backup time score",  "legendValue": 71, "values": []},
        {"key": "loadPressure", "color": "#7e6ea1", "dashed": False, "label": "Load Pressure score", "legendValue": 85, "values": []},
        {"key": "headroom",     "color": "#9c8235", "dashed": True,  "label": "Load Headroom",       "legendValue": 43, "values": []},
    ]}}


def _rawstripped_meta():
    """A raw==stripped metadata payload (compound presentation/ordering keys): a leaf byte-identical between raw and
    stripped is METADATA → CLASS 4 must keep it verbatim (root-cause raw-vs-stripped wall)."""
    return {"trend": {"pres": {"stackOrder": ["sag", "swell", "current", "neutral"],
                               "lineOrder": ["vWorst", "iWorst"],
                               "titleConnector": " at ", "leftAxisLabel": "No. of Events"}},
            "table": {"pres": {"columnOrder": ["panel", "events", "voltage", "cause"]}}}


# Each fixture is a self-contained guard-input snapshot. `logged`: None|bool|{col:bool} drives neuract.column_logged;
# `has_rows` drives latest_ts (the CLASS-2 conclusiveness gate); `rating_keys` drives the nameplate slot map;
# `binding_returns` drives the derivation-binding resolver; `cfg_overrides` pins DB knobs for THIS fixture (merged over
# the code defaults). `expected_gaps` is the authoring intent — the baseline records the ACTUAL gaps and flags a
# mismatch so a mis-authored fixture is caught at --baseline time.
CORPUS = [
    {  # CLASS 1 — epoch scalar + all-epoch array blank; a …indexes time axis + a real reading are exempt
        "name": "class1_epoch_scalar_array_time_axis_exempt",
        "out": {"data": {"maxLine": {"value": _EPOCH},
                         "expectedMax": [_EPOCH, _EPOCH2],
                         "xLabelIndexes": [1783193400000, 1783197000000],
                         "voltage": 238.6, "power": 0.0}},
        "expected_gaps": [{"cause": "epoch_ms_leak", "slot": "data.maxLine.value"},
                          {"cause": "epoch_ms_leak", "slot": "data.expectedMax"}],
    },
    {  # CLASS 1 — a per-point object's `value` key holding epoch ms blanks; the point's own `time` axis is exempt
        "name": "class1_epoch_series_object_value_key",
        "out": {"series": [{"time": _EPOCH, "value": _EPOCH}, {"time": _EPOCH2, "value": _EPOCH2}]},
        "expected_gaps": [{"cause": "epoch_ms_leak", "slot": "series[0].value"},
                          {"cause": "epoch_ms_leak", "slot": "series[1].value"}],
    },
    {  # CLASS 2 — all-null column reading blanks; a present-and-LOGGED column's real 0.0 is exempt
        "name": "class2_null_column_present_logged_exempt",
        "out": {"snapshot": {"vThd": {"valuePct": 0.0}, "iThd": {"valuePct": 0.0}}},
        "fields": [{"slot": "snapshot.vThd.valuePct", "kind": "raw", "column": "thd_compliance_v_avg", "label": "V-THD"},
                   {"slot": "snapshot.iThd.valuePct", "kind": "raw", "column": "thd_compliance_i_avg", "label": "I-THD"}],
        "present_cols": ["thd_compliance_v_avg", "thd_compliance_i_avg"],
        "logged": {"thd_compliance_v_avg": False, "thd_compliance_i_avg": True},
        "has_rows": True,
        "expected_gaps": [{"cause": "null_column_reading", "slot": "snapshot.vThd.valuePct"}],
    },
    {  # CLASS 2 — DB-outage conclusiveness gate: column_logged False but table has NO rows → inconclusive → NO blank
        "name": "class2_db_outage_no_over_reach",
        "out": {"snapshot": {"v": {"valuePct": 238.6}}},
        "fields": [{"slot": "snapshot.v.valuePct", "kind": "raw", "column": "v_avg", "label": "V"}],
        "present_cols": ["v_avg"],
        "logged": False, "has_rows": False,
        "expected_gaps": [],
    },
    {  # CLASS 3 — a no-source numeric leaf (no column / fn / binding / rating) is a stray → blank
        "name": "class3_no_source_numeric",
        "out": {"snapshot": {"iThdPk": 265.0}},
        "fields": [{"slot": "snapshot.iThdPk", "kind": "raw", "column": None, "label": "iThd Peak"}],
        "present_cols": [], "logged": True,
        "expected_gaps": [{"cause": "no_source_value", "slot": "snapshot.iThdPk"}],
    },
    {  # CLASS 3 — a const/text literal (axis chrome, source not 'live') is AI-authored chrome → never policed
        "name": "class3_const_literal_chrome_preserved",
        "out": {"axis": {"label": "-29d"}},
        "fields": [{"slot": "axis.label", "kind": "const", "value": "-29d"}],
        "present_cols": [],
        "expected_gaps": [],
    },
    {  # LIVE-LITERAL — a const/text leaf CLAIMING source='live' with no column/rating (a string dressed as a reading)
        "name": "live_literal_string_blanks",
        "out": {"panel": {"tapPosition": "AUTO"}},
        "fields": [{"slot": "panel.tapPosition", "kind": "const", "source": "live", "value": "AUTO",
                    "label": "Tap Position"}],
        "present_cols": [], "rating_keys": {},
        "expected_gaps": [{"cause": "no_source_value", "slot": "panel.tapPosition"}],
    },
    {  # LIVE-LITERAL — a const source='live' leaf that RESOLVES a real nameplate rating has a source → preserved
        "name": "live_literal_nameplate_rating_exempt",
        "out": {"nameplate": {"ratedKva": "600 kVA"}},
        "fields": [{"slot": "nameplate.ratedKva", "kind": "const", "source": "live", "value": "600 kVA"}],
        "present_cols": [], "rating_keys": {"nameplate.ratedKva": "rated_kva"},
        "expected_gaps": [],
    },
    {  # CLASS 4 — card-73 legendValue seed [52,71,85,43] blanks; structural chrome (key/color/label) survives
        "name": "class4_legendvalue_seed_blanks_chrome_survives",
        "out": _card73_default(),
        "default_payload": _card73_default(),
        "written_paths": [],
        "expected_gaps": [{"cause": "unstripped_seed", "slot": f"backupHistory.series[{i}].legendValue"}
                          for i in range(4)],
    },
    {  # CLASS 4 — raw==stripped metadata (order/connector/axis-label) is kept verbatim → ZERO blanks
        "name": "class4_raw_equals_stripped_metadata_kept",
        "out": _rawstripped_meta(),
        "default_payload": _rawstripped_meta(),
        "shape_ref": _rawstripped_meta(),
        "written_paths": [],
        "expected_gaps": [],
    },
    {  # WRITER-AWARE CLASS 2 — a panel-aggregate fill (agg_row_present) whose value came from the member roll-up:
       # CLASS 2's asset_table column-logged audit is invalid → stands down (flag null_column_writer_aware on)
        "name": "class2_writer_aware_agg_row_skips",
        "out": {"card": {"value": 3270.0}},
        "fields": [{"slot": "card.value", "kind": "raw", "column": "apparent_power_total_kva", "label": "Live kVA"}],
        "present_cols": ["apparent_power_total_kva"],
        "logged": {"apparent_power_total_kva": False}, "has_rows": True,
        "agg_row_present": True,
        "cfg_overrides": {"fab_guards.null_column_writer_aware": "on"},
        "expected_gaps": [],
    },
    {  # ROSTER-SLOT EXEMPTION — a roster-written value inside a recipe slot survives its mis-declared absent-column
       # field (flag exempt_roster_slots on); a stray OUTSIDE the roster slots is still blanked
        "name": "roster_slot_exemption",
        "out": {"card": {"view": {"value": 3270.0, "metrics": [{"id": "active", "value": 3037.3}]}},
                "stray": {"leaf": 265.0}},
        "fields": [{"slot": "card.view.value", "kind": "raw", "column": "apparent_power_total_kva", "label": "Live kVA"},
                   {"slot": "stray.leaf", "kind": "raw", "column": None, "label": "stray"}],
        "present_cols": [], "logged": True,
        "roster_slot_prefixes": ["card.view.value", "card.view.metrics"],
        "cfg_overrides": {"fab_guards.exempt_roster_slots": "on"},
        "expected_gaps": [{"cause": "no_source_value", "slot": "stray.leaf"}],
    },
]

# per-CLASS knob matrix: re-run the whole corpus with each guard valve flipped OFF and with report mode, so a
# knob-semantics regression (a valve that no longer gates, a report mode that mutates) is caught alongside the fixtures.
KNOB_SCENARIOS = [
    ("guard_off:epoch_ms", {"fab_guards.epoch_ms": "off"}),
    ("guard_off:null_column", {"fab_guards.null_column": "off"}),
    ("guard_off:no_source", {"fab_guards.no_source": "off"}),
    ("guard_off:seed_leak", {"fab_guards.seed_leak": "off"}),
    ("mode:report", {"fab_guards.mode": "report"}),
]


# ── deterministic offline stubs ─────────────────────────────────────────────────────────────────────────────────────
def _cfg_stub(overrides):
    """A config.app_config.cfg(key, default) that returns overrides[key] when pinned, else the passed default (the
    DB-miss path). Drives EVERY guard knob — cfg-based (_guard_on/_mode/_epoch_floor/vocab) AND flag_on-based
    (live_literal/exempt_roster_slots/null_column_writer_aware), since flag_on resolves through this same cfg."""
    def _c(key, default=None):
        return overrides[key] if key in overrides else default
    return _c


@contextlib.contextmanager
def _stubs(fx, extra_cfg=None):
    """Patch neuract + slot map + binding resolver + reason renderer + every DB knob for one fixture replay. All
    patches are by-name so the guards' lazy `from ... import` picks them up at call time (the module-attr pattern the
    unit tests rely on)."""
    logged = fx.get("logged")

    def _column_logged(_t, c):
        if isinstance(logged, dict):
            return bool(logged.get(c, True))
        return True if logged is None else bool(logged)

    has_rows = fx.get("has_rows", True)
    present = frozenset(fx.get("present_cols") or [])
    rating_keys = fx.get("rating_keys") or {}
    binding = fx.get("binding_returns")
    overrides = dict(fx.get("cfg_overrides") or {})
    if extra_cfg:
        overrides.update(extra_cfg)

    with contextlib.ExitStack() as es:
        es.enter_context(mock.patch("config.app_config.cfg", _cfg_stub(overrides)))
        es.enter_context(mock.patch("ems_exec.data.neuract.column_logged", _column_logged))
        es.enter_context(mock.patch("ems_exec.data.neuract.latest_ts",
                                    lambda _t: ("2026-07-06T00:00:00" if has_rows else None)))
        es.enter_context(mock.patch("ems_exec.data.neuract.present_columns", lambda _t: present))
        es.enter_context(mock.patch("config.nameplate_slot_map.rating_key_for", lambda s: rating_keys.get(s)))
        es.enter_context(mock.patch("ems_exec.executor.indexed_families._binding_for_field", lambda _f: binding))
        es.enter_context(mock.patch("config.reason_templates.sentence", lambda cause, **_kw: cause))
        yield


def _replay(fx, extra_cfg=None):
    """One fixture through fab_guards.apply(). Returns (sorted [(cause, slot), ...], out_mutated)."""
    with _stubs(fx, extra_cfg=extra_cfg):
        G._ROWS_CACHE.clear()                        # CLASS-2 logged cache — clear between fixtures (tests do the same)
        before = copy.deepcopy(fx["out"])
        out = copy.deepcopy(fx["out"])
        out, gaps = G.apply(
            out, fx.get("fields") or [], frozenset(fx.get("present_cols") or []), fx.get("asset_table", "tbl"),
            default_payload=fx.get("default_payload"), written_paths=fx.get("written_paths"),
            shape_ref=fx.get("shape_ref"), roster_slot_prefixes=fx.get("roster_slot_prefixes"),
            card_id=fx.get("card_id"), agg_row_present=fx.get("agg_row_present", False))
    tuples = sorted((str(g.get("cause")), str(g.get("slot"))) for g in gaps)
    return tuples, (out != before)


# ── baseline build + diff ───────────────────────────────────────────────────────────────────────────────────────────
def _sha_pkg(dirpath):
    """Stable sha over a package dir: sorted .py basenames, contents concatenated (provenance only, never gated)."""
    try:
        names = sorted(n for n in os.listdir(dirpath) if n.endswith(".py"))
        h = hashlib.sha256()
        for n in names:
            with open(os.path.join(dirpath, n), "rb") as f:
                h.update(f.read())
        return h.hexdigest()[:16] if names else None
    except OSError:
        return None


def build_baseline():
    fixtures, mismatches = {}, []
    for fx in CORPUS:
        tuples, mutated = _replay(fx)
        expect = sorted((str(g["cause"]), str(g["slot"])) for g in (fx.get("expected_gaps") or []))
        ok = tuples == expect
        if not ok:
            mismatches.append(fx["name"])
        fixtures[fx["name"]] = {"gaps": [list(t) for t in tuples], "out_mutated": mutated,
                                "expected_gaps": [list(t) for t in expect], "expected_match": ok}
    knob_matrix = {}
    for scenario, extra in KNOB_SCENARIOS:
        per = {}
        for fx in CORPUS:
            tuples, mutated = _replay(fx, extra_cfg=extra)
            per[fx["name"]] = {"gaps": [list(t) for t in tuples], "out_mutated": mutated}
        knob_matrix[scenario] = per
    baseline = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tool": "tools/guard_corpus_replay.py",
        "acceptance_standard": "all fabrications caught, zero legit values harmed — diff fixtures + knob_matrix vs this "
                               "committed baseline after every fab_guards change; a new blank must be a real "
                               "fabrication, a vanished blank an intended release",
        "guards_provenance": {"ems_exec/executor/fab_guards": _sha_pkg(
            os.path.join(ROOT, "ems_exec", "executor", "fab_guards"))},
        "fixtures": fixtures,
        "knob_matrix": knob_matrix,
    }
    return baseline, mismatches


def _diff(baseline, current):
    """Return a list of drift lines (empty == identical). Compares the deterministic parts only (gaps + out_mutated,
    per fixture and per knob scenario) — never `generated` or provenance sha."""
    drifts = []
    bf, cf = baseline.get("fixtures", {}), current.get("fixtures", {})
    for name in sorted(set(bf) | set(cf)):
        b, c = bf.get(name), cf.get(name)
        if b is None:
            drifts.append(f"fixture ADDED (not in baseline): {name}")
            continue
        if c is None:
            drifts.append(f"fixture DROPPED (in baseline, not replayed): {name}")
            continue
        if b.get("gaps") != c.get("gaps"):
            drifts.append(f"[{name}] gaps: {b.get('gaps')} -> {c.get('gaps')}")
        if b.get("out_mutated") != c.get("out_mutated"):
            drifts.append(f"[{name}] out_mutated: {b.get('out_mutated')} -> {c.get('out_mutated')}")
    bm, cm = baseline.get("knob_matrix", {}), current.get("knob_matrix", {})
    for scen in sorted(set(bm) | set(cm)):
        bs, cs = bm.get(scen, {}), cm.get(scen, {})
        for name in sorted(set(bs) | set(cs)):
            if bs.get(name) != cs.get(name):
                drifts.append(f"[knob {scen}][{name}] {bs.get(name)} -> {cs.get(name)}")
    return drifts


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--baseline", action="store_true", help="WRITE the committed baseline (else replay + diff it)")
    ap.add_argument("--out", default=_BASELINE, help="baseline path")
    args = ap.parse_args(argv)

    current, mismatches = build_baseline()
    n_fx, n_scen = len(current["fixtures"]), len(current["knob_matrix"])

    if args.baseline:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(current, f, indent=1, sort_keys=True)
            f.write("\n")
        blanked = sum(1 for v in current["fixtures"].values() if v["gaps"])
        print(f"guard_corpus_replay: wrote baseline ({n_fx} fixtures, {n_scen} knob scenarios, "
              f"{blanked} fixtures produce gaps) -> {os.path.relpath(args.out, ROOT)}")
        if mismatches:
            print("WARNING: fixtures whose ACTUAL gaps != declared expected_gaps (review the corpus): "
                  + ", ".join(mismatches))
        return 0

    try:
        with open(args.out, encoding="utf-8") as f:
            baseline = json.load(f)
    except (OSError, ValueError) as e:
        print(f"guard_corpus_replay: no committed baseline at {os.path.relpath(args.out, ROOT)} "
              f"({type(e).__name__}) — run with --baseline first")
        return 1

    drifts = _diff(baseline, current)
    if drifts:
        print(f"guard_corpus_replay: DRIFT — {len(drifts)} change(s) vs the committed baseline:")
        for d in drifts:
            print("  " + d)
        return 1
    print(f"guard_corpus_replay: OK — {n_fx} fixtures + {n_scen} knob scenarios identical to the committed baseline")
    return 0


if __name__ == "__main__":
    sys.exit(main())
