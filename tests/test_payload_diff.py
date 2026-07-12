"""tests/test_payload_diff.py — tools/payload_diff pure logic: execution segmentation of appended run logs, the
structural/value/emptied deep-diff classes, card alignment (incl. multi-asset tags + duplicate ids), the ref grammar,
and the end-to-end compare() report over two synthetic snapshots (a swap, a REAL→EMPTY leaf, a knob change, an SQL
delta). All offline — no DB, no host."""
import json
import os

from tools.payload_diff import deep_diff as D
from tools.payload_diff import extract as X
from tools.payload_diff import logs as L
from tools.payload_diff import refs as R
from tools.payload_diff.align import align
from tools.payload_diff.diff import compare
from tools.payload_diff import report_html, report_term


# ── logs: segmentation ────────────────────────────────────────────────────────────────────────────────────────────────
def _rec(stage, ts, **f):
    return {"ts": ts, "stage": stage, **f}


def test_segment_executions_splits_on_prompt():
    log = [_rec("PROMPT", 1.0), _rec("1a", 2.0), _rec("RESPONSE", 3.0),
           _rec("PROMPT", 10.0), _rec("RESPONSE", 12.0)]
    segs = L.segment_executions(log)
    assert len(segs) == 2
    assert [r["stage"] for r in segs[0]] == ["PROMPT", "1a", "RESPONSE"]
    assert segs[1][0]["ts"] == 10.0


def test_segment_executions_leading_records_and_no_prompt():
    # multi-asset RESPONSE_MULTI logs under the parent rid with no PROMPT record of its own
    log = [_rec("RESPONSE_MULTI", 5.0)]
    assert len(L.segment_executions(log)) == 1
    log2 = [_rec("RESPONSE_MULTI", 5.0), _rec("PROMPT", 8.0), _rec("RESPONSE", 9.0)]
    segs = L.segment_executions(log2)
    assert len(segs) == 2 and segs[0][0]["stage"] == "RESPONSE_MULTI"
    assert L.segment_executions([]) == []


def test_segment_time_window_pads():
    seg = [_rec("PROMPT", 10.0), _rec("RESPONSE", 20.0)]
    lo, hi = L.segment_time_window(seg, pad_s=2.0)
    assert lo == 8.0 and hi == 22.0


def test_make_run_id_matches_pipeline():
    from run.run_id import make_run_id as pipeline_make
    assert L.make_run_id("energy for UPS-01") == pipeline_make("energy for UPS-01")


# ── deep_diff: classes ────────────────────────────────────────────────────────────────────────────────────────────────
def test_deep_diff_structural_vs_value():
    a = {"title": "Energy", "kpi": 5, "gone": 1}
    b = {"title": "Energy", "kpi": 7, "new": 2}
    kinds = {e["path"]: (e["kind"], e["cls"]) for e in D.diff(a, b)}
    assert kinds["kpi"] == ("value", "value")
    assert kinds["gone"] == ("removed", "structural")
    assert kinds["new"] == ("added", "structural")


def test_deep_diff_emptied_and_filled():
    entries = D.diff({"v": 42, "w": None}, {"v": "—", "w": 3})
    subs = {e["path"]: e.get("sub") for e in entries}
    assert subs["v"] == "emptied" and subs["w"] == "filled"


def test_deep_diff_scalar_series_collapses():
    a = {"series": [1, 2, 3, 4]}
    b = {"series": [1, 9, 3, 8]}
    entries = D.diff(a, b)
    assert len(entries) == 1 and entries[0]["kind"] == "series"
    assert entries[0]["b"]["changed"] == 2


def test_deep_diff_series_length_is_structural():
    entries = D.diff({"s": [1, 2, 3]}, {"s": [1, 2]})
    assert any(e["kind"] == "length" and e["cls"] == "structural" for e in entries)


def test_deep_diff_tolerance_mutes_jitter():
    assert D.diff({"v": 100.0}, {"v": 101.0}, tol=0.02) == []
    assert D.diff({"v": 100.0}, {"v": 110.0}, tol=0.02) != []


def test_deep_diff_none_vs_value_is_emptied_not_type():
    entries = D.diff({"v": 5}, {"v": None})
    assert entries[0]["sub"] == "emptied" and entries[0]["cls"] == "value"


def test_deep_diff_caps_entries():
    a = {str(i): i for i in range(500)}
    entries = D.diff(a, {}, max_entries=50)
    assert len(entries) <= 51 and entries[-1]["kind"] in ("removed", "truncated")


# ── align + card_key ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_card_key_multi_asset_and_align():
    ca = {"card_id": 39, "asset": {"id": 11, "name": "UPS-01"}}
    cb = {"card_id": 39, "asset": {"id": 12, "name": "UPS-02"}}
    assert X.card_key(ca) != X.card_key(cb)
    paired, only_a, only_b = align({"c39": 1, "c40": 2}, {"c39": 3, "c41": 4})
    assert paired == ["c39"] and only_a == ["c40"] and only_b == ["c41"]


def test_cards_view_disambiguates_duplicate_ids():
    snap = {"response": {"cards": [{"card_id": 5, "title": "A"}, {"card_id": 5, "title": "B"}]}}
    view = X.cards_view(snap)
    assert len(view) == 2


# ── refs grammar ─────────────────────────────────────────────────────────────────────────────────────────────────────
def test_ref_parse_occurrence():
    assert R.parse("r_0123456789@-2") == ("r_0123456789", -2)
    assert R.parse("energy for UPS-01@0") == ("energy for UPS-01", 0)
    assert R.parse("plain prompt") == ("plain prompt", None)


# ── sql view ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_sql_view_groups_and_tags_db():
    snap = {"sql": [
        {"sql": "SELECT  a FROM t1\n WHERE x", "db": "neuract", "ms": 3, "rows": 2},
        {"sql": "SELECT a FROM t1 WHERE x", "db": "neuract", "ms": 1, "rows": 2},
        {"sql": "SELECT key FROM app_config", "db": "cmd_catalog", "ms": 1, "rows": 9},
    ]}
    view = X.sql_view(snap)
    neuract_key = "SELECT a FROM t1 WHERE x"
    assert view[neuract_key]["n"] == 2 and view[neuract_key]["table"] == "t1"
    assert "[cmd_catalog] SELECT key FROM app_config" in view


# ── end-to-end compare() over synthetic snapshots ────────────────────────────────────────────────────────────────────
def _snap(cards, run_id="r_aaaaaaaaaa", occ=0, cfg=None, sql=None, verdict="pass"):
    return {
        "snapshot_version": 1,
        "meta": {"run_id": run_id, "prompt": "p", "occurrence": occ, "captured_at": "t",
                 "source": "test", "label": None, "git": {"sha": "abc", "dirty": False}},
        "response": {"prompt": "p", "run_id": run_id,
                     "page": {"page_key": "shell/x", "layout": {"layout_primitive": "grid"}, "groups": []},
                     "asset": {"asset": {"name": "UPS-01"}, "how": "AI"},
                     "validation": {"verdict": verdict}, "cards": cards},
        "stages": [_rec("PROMPT", 1.0, text="p"), _rec("RESPONSE", 9.0)],
        "sql": sql or [], "app_config": cfg or {}, "unavailable": {} if sql else {"sql": "no trace"},
    }


def _card(cid, kpi=5, verdict="render", real=3, swap="keep"):
    return {"card_id": cid, "render_card_id": cid, "title": f"Card {cid}", "slot": cid, "size": "m",
            "swap": {"action": swap, "origin": "kept", "swap_to_id": None},
            "endpoint": "energy-power-history", "is_history": True, "conforms": True,
            "data_instructions": {"fields": [{"column": "kwh_total"}], "consumer": {"endpoint": "energy-power-history"}},
            "render": {"verdict": verdict, "answerability": "partial", "leaf_stats": {"real": real, "data": 4}},
            "payload": {"variant": "baseline", "kpi": kpi, "series": [1, 2, 3]},
            "has_payload": True, "payload_error": None, "fill_ok": True}


def test_compare_full_report():
    a = _snap([_card(1), _card(2)], cfg={"reflect.min_gap_frac": "0.34"},
              sql=[{"sql": "SELECT a FROM t", "db": "neuract", "ms": 1, "rows": 5, "ts": 2.0}])
    b_cards = [_card(1, kpi=9, verdict="honest_blank", real=0), _card(3, swap="swap")]
    b = _snap(b_cards, run_id="r_bbbbbbbbbb", cfg={"reflect.min_gap_frac": "0.50"},
              sql=[{"sql": "SELECT b FROM t2", "db": "neuract", "ms": 1, "rows": 0, "ts": 2.0}])
    rep = compare(a, b)
    assert rep["page"]["same"] is True                     # same page fields
    assert rep["cards"]["only_a"] == ["c2"] and rep["cards"]["only_b"] == ["c3"]
    assert rep["validation"]["regressions"] == 1           # c1: render → honest_blank, real 3 → 0
    assert any(ch["key"] == "reflect.min_gap_frac" for ch in rep["config"]["changes"])
    assert len(rep["sql"]["added"]) == 1 and len(rep["sql"]["removed"]) == 1
    kpi_entries = [e for c in rep["payload"]["cards"] for e in c["entries"] if e["path"] == "kpi"]
    assert kpi_entries and kpi_entries[0]["cls"] == "value"
    # both renderers accept the report
    term = report_term.render(rep)
    assert "REAL→EMPTY" in term or "regression" in term
    html = report_html.render(rep)
    assert "<!doctype html>" in html and "regression" in html


def test_compare_degrades_without_response():
    a = _snap([_card(1)], cfg={"site.name": "PEGEPL"})
    b = _snap([_card(1)], cfg={"site.name": "PEGEPL"})
    b["response"] = None
    b["unavailable"]["response"] = "occurrence predates the latest response"
    rep = compare(a, b)
    assert "unavailable" in rep["payload"] and "unavailable" in rep["page"]
    assert "unavailable" not in rep["config"]              # config still diffs
    report_term.render(rep)                                # renders without crashing
    report_html.render(rep)


def test_snapshot_build_from_logs(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "LOG_DIR", str(tmp_path))
    rid = "r_0000000000"
    with open(os.path.join(str(tmp_path), f"pipeline_{rid}.jsonl"), "w") as f:
        for rec in [_rec("PROMPT", 1.0, text="'p1'"), _rec("RESPONSE", 5.0),
                    _rec("PROMPT", 10.0, text="'p1'"), _rec("RESPONSE", 15.0)]:
            f.write(json.dumps(rec) + "\n")
    with open(os.path.join(str(tmp_path), f"sql_{rid}.jsonl"), "w") as f:
        f.write(json.dumps({"ts": 11.0, "sql": "SELECT 1", "db": "neuract", "rows": 1, "ms": 1}) + "\n")
        f.write(json.dumps({"ts": 3.0, "sql": "SELECT 2", "db": "neuract", "rows": 1, "ms": 1}) + "\n")
    with open(os.path.join(str(tmp_path), f"response_{rid}.json"), "w") as f:
        json.dump({"prompt": "p1", "run_id": rid, "cards": []}, f)
    from tools.payload_diff import snapshot as S
    snap = S.build(rid, occurrence=-1)
    assert snap["meta"]["occurrence"] == 1 and snap["meta"]["executions_in_log"] == 2
    assert snap["response"] is not None
    assert [r["sql"] for r in snap["sql"]] == ["SELECT 1"]  # only the latest execution's window
    older = S.build(rid, occurrence=0)
    assert older["response"] is None and "response" in older["unavailable"]
    assert [r["sql"] for r in older["sql"]] == ["SELECT 2"]
