"""tests/test_admin_console.py — the admin console's read layer: store cache, run summaries, trace assembly,
AI stage attribution, failure search, replay id prediction. Fixture runs use non-hex ids (r_testadmin*) so they are
DEV NOISE to the real console (run_ids('real') filters them) — the tests read them via files_for/sink='all'."""
import json
import os
import time

from admin import ai_usage, config, failures_report, runs, store, trace


RID = "r_testadmin1"


def _write(path, lines):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        if isinstance(lines, list):
            f.write("\n".join(json.dumps(x) for x in lines) + "\n")
        else:
            json.dump(lines, f)


def _fixture_run(rid=RID):
    t0 = time.time()
    logs = config.LOGS_DIR
    _write(os.path.join(logs, f"pipeline_{rid}.jsonl"), [
        {"ts": t0, "stage": "PROMPT", "text": "'test prompt one'", "asset_id": None},
        {"ts": t0 + 1.0, "stage": "1a", "page": "asset-overview", "cards": 3, "metric": "power"},
        {"ts": t0 + 1.5, "stage": "1b", "asset": "UPS-9", "mfm_id": 9, "how": "AI", "candidates": 0, "basket_cols": 4},
        {"ts": t0 + 2.0, "stage": "validate", "verdict": "pass", "expected_gap_frac": 0.0},
        {"ts": t0 + 9.0, "stage": "RESPONSE", "page": "asset-overview", "cards": 3, "with_payload": 3,
         "rendered": 2, "partial": 1, "blank": 0, "asset_pending": False, "elapsed_ms": 9000},
        # a SECOND execution of the same prompt (deterministic id appends)
        {"ts": t0 + 100.0, "stage": "PROMPT", "text": "'test prompt one'", "asset_id": 9},
        {"ts": t0 + 109.0, "stage": "RESPONSE", "page": "asset-overview", "cards": 3, "with_payload": 3,
         "rendered": 3, "partial": 0, "blank": 0, "asset_pending": False, "elapsed_ms": 9000},
    ])
    _write(os.path.join(logs, f"ai_{rid}.jsonl"), [
        {"ts": "2026-07-11T00:00:01", "run_id": rid, "url": "http://localhost:8200/v1/chat/completions",
         "request": {"model": "m", "messages": [
             {"role": "system", "content": "You are the L1 ASSET RESOLVER for tests"},
             {"role": "user", "content": "which asset"}]},
         "response": {"choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}],
                      "usage": {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110}}},
        {"ts": "2026-07-11T00:00:05", "run_id": rid, "url": "http://localhost:8200/v1/chat/completions",
         "request": {"model": "m", "messages": [
             {"role": "system", "content": "You are LAYER 2 of a dashboard-composition pipeline"},
             {"role": "user", "content": "emit card"}]},
         "response": {"choices": [{"message": {"content": "{\"a\":1}"}, "finish_reason": "stop"}],
                      "usage": {"prompt_tokens": 200, "completion_tokens": 20, "total_tokens": 220}}},
    ])
    _write(os.path.join(logs, f"failures_{rid}.jsonl"), [
        {"ts": "2026-07-11T00:00:03", "run_id": rid, "stage": "llm", "card_id": None, "group_id": None,
         "reason": "timeout", "detail": "stage=l2_emit needle-xyz"},
    ])
    _write(os.path.join(logs, f"sql_{rid}.jsonl"), [
        {"ts": time.time(), "db": "neuract", "sql": "SELECT 1 FROM gic_x", "rows": 1, "ms": 12},
    ])
    _write(os.path.join(logs, f"response_{rid}.json"), {
        "ok": True, "prompt": "test prompt one", "run_id": rid, "elapsed_ms": 9000,
        "page": {"page_key": "asset-overview", "page_title": "Asset Overview"},
        "asset": {"asset": {"mfm_id": 9, "name": "UPS-9", "class": "UPS"}, "how": "AI", "candidates": []},
        "validation": {"verdict": "pass", "how": "AI", "policy": "annotate",
                       "data_summary": {"n_columns": 4, "n_pass": 4, "n_warn": 0, "n_fail": 0},
                       "payload_summary": {}},
        "cards": [{"card_id": 1, "title": "KPI", "render": {"verdict": "render", "answerability": "full",
                   "leaf_stats": {"real": 5, "data": 5, "undeclared": 0}}}],
        "asset_pending": False, "notes": {}, "errors": {},
    })
    return rid


def test_store_cached_reparses_on_change(tmp_path):
    p = tmp_path / "x.jsonl"
    p.write_text('{"a": 1}\n')
    assert store.cached(str(p), store.jsonl) == [{"a": 1}]
    time.sleep(0.01)
    p.write_text('{"a": 1}\n{"a": 2}\n')
    assert len(store.cached(str(p), store.jsonl)) == 2


def test_jsonl_skips_torn_lines(tmp_path):
    p = tmp_path / "torn.jsonl"
    p.write_text('{"ok": 1}\n{"broken": \n')
    assert store.jsonl(str(p)) == [{"ok": 1}]


def test_run_ids_filters_dev_noise():
    _fixture_run()
    assert RID not in store.run_ids("real")          # non-hex id = dev noise, hidden by default
    assert RID in store.run_ids("all")


def test_executions_split_and_summary():
    _fixture_run()
    execs = runs.executions(RID)
    assert len(execs) == 2                            # split at each PROMPT
    s = runs.summary(RID)
    assert s["prompt"] == "test prompt one"
    assert s["page_key"] == "asset-overview"
    assert s["executions"] == 2
    assert s["rendered"] == 3                         # LAST execution wins
    assert s["n_ai_calls"] == 2 and s["prompt_tokens"] == 300
    assert s["n_failures"] == 1 and s["n_sql"] == 1


def test_trace_build_assembles_all_sinks():
    _fixture_run()
    t = trace.build(RID)
    assert len(t["timeline"]) == 2
    recs = t["timeline"][0]["records"]
    assert recs[0]["stage"] == "PROMPT" and recs[1]["dur_ms"] is not None
    assert len(t["ai_calls"]) == 2 and len(t["sql"]) == 1 and len(t["failures"]) == 1
    assert t["response"]["cards"][0]["verdict"] == "render"
    call = trace.ai_call_detail(RID, 1)
    assert call["response"]["usage"]["total_tokens"] == 220


def test_ai_stage_attribution():
    _fixture_run()
    calls = ai_usage.calls_for(RID)
    assert calls[0]["stage"] == "1b.asset_resolve"
    assert calls[1]["stage"] == "l2_emit"


def test_failures_search_finds_detail_substring():
    _fixture_run()
    # dev-noise runs are excluded from the global report; search the rows door directly
    rows = failures_report._rows(RID)
    assert any("needle-xyz" in (r["detail"] or "") for r in rows)


def test_window_params_inclusive_to_day():
    t_from, t_to = config.window_params({"from": ["2026-07-01"], "to": ["2026-07-02"]})
    assert t_to - t_from == 2 * 86400                 # date-only `to` includes the whole day


def test_replay_predicts_run_id():
    from admin.replay import _predict_run_id
    from run.run_id import make_run_id
    assert _predict_run_id("hello world") == make_run_id("hello world")
