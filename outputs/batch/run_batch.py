"""outputs/batch/run_batch.py — run every prompt in prompts.json through the live host /api/run with
bounded concurrency, capture a STRUCTURED per-prompt result, and log all. Thread-safe: the host is a
ThreadingHTTPServer and run_pipeline shells psql per query (no shared conn) → concurrency is safe.

Captures per prompt: 1a page, 1b asset+class, card/payload counts, swapped cards, per-endpoint frame
{ok,buckets}, asset_pending, error, elapsed. Writes:
  - results.jsonl   (one structured line per prompt — the machine log)
  - progress.log    (human-tailable live progress)
  - summary.json    (coverage rollups: classes/pages/intents/cols hit, failures)
The pipeline ALSO auto-logs each run to outputs/logs/pipeline_<run_id>.jsonl (obs/stage)."""
import json
import os
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = os.path.dirname(__file__)
HOST = os.environ.get("HOST_URL", "http://127.0.0.1:8770/api/run")
CONC = int(os.environ.get("BATCH_CONCURRENCY", "3"))
TIMEOUT = int(os.environ.get("BATCH_TIMEOUT", "240"))

TAG = os.environ.get("BATCH_TAG", "")            # e.g. "_v2" -> results_v2.jsonl, isolates a re-run's outputs
PROMPTS = json.load(open(os.environ.get("BATCH_PROMPTS", os.path.join(HERE, "prompts.json"))))
RESULTS = os.path.join(HERE, f"results{TAG}.jsonl")
PROGRESS = os.path.join(HERE, f"progress{TAG}.log")
SUMMARY = os.path.join(HERE, f"summary{TAG}.json")

_log_lock = __import__("threading").Lock()


def _post(prompt):
    body = json.dumps({"prompt": prompt}).encode()
    req = urllib.request.Request(HOST, data=body, headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        d = json.loads(r.read())
    return d, round(time.time() - t0, 1)


def _frame_len(fr):
    """count rows/buckets in a frame regardless of shape (history|buckets|series|rows|data)."""
    if not isinstance(fr, dict):
        return None
    for k in ("history", "buckets", "series", "rows", "data", "samples"):
        v = fr.get(k)
        if isinstance(v, list):
            return len(v)
    return 0


def _digest(p, d, elapsed):
    """Reduce the big /api/run response to the fields that prove the pipeline worked for this prompt.
    Response shape: {ok, page{page_key,intent,metric,..}, asset{asset{name,class,..},candidates}, asset_pending,
    cards[{card_id,render_card_id,endpoint,is_history,has_payload,swap}], frames{endpoint:frame}, elapsed_ms}."""
    cards = d.get("cards") or []
    page = d.get("page") or {}
    asset = (d.get("asset") or {}).get("asset") or {}
    frames = d.get("frames") or {}
    frame_digest = {ep: {"type": (fr or {}).get("type") if isinstance(fr, dict) else None,
                         "rows": _frame_len(fr)} for ep, fr in frames.items()}
    endpoints = sorted({c.get("endpoint") for c in cards if c.get("endpoint")})
    return {
        "id": p["id"], "prompt": p["prompt"], "want_asset": p["asset"], "want_klass": p["klass"],
        "want_intent": p["intent"], "want_page": p["page_hint"], "want_cols": p["metric_cols"],
        "ok": True, "elapsed_s": elapsed,
        "got_page": page.get("page_key"), "got_intent": page.get("intent"), "got_metric": page.get("metric"),
        "got_asset": asset.get("name"), "got_class": asset.get("class"), "got_mfm": asset.get("mfm_id"),
        "asset_pending": d.get("asset_pending", False),
        "n_candidates": len((d.get("asset") or {}).get("candidates") or []),
        "n_cards": len(cards), "n_payload": sum(1 for c in cards if c.get("has_payload")),
        "n_history_cards": sum(1 for c in cards if c.get("is_history")),
        "n_swapped": sum(1 for c in cards if c.get("render_card_id") and c.get("render_card_id") != c.get("card_id")),
        "endpoints": endpoints, "frames": frame_digest,
        "run_id": d.get("run_id"),
    }


def _run_one(p):
    try:
        d, elapsed = _post(p["prompt"])
        rec = _digest(p, d, elapsed)
    except Exception as e:
        rec = {"id": p["id"], "prompt": p["prompt"], "want_asset": p["asset"], "want_klass": p["klass"],
               "want_intent": p["intent"], "want_page": p["page_hint"], "want_cols": p["metric_cols"],
               "ok": False, "error": f"{type(e).__name__}: {str(e)[:160]}"}
    with _log_lock:
        with open(RESULTS, "a") as f:
            f.write(json.dumps(rec) + "\n")
        with open(PROGRESS, "a") as f:
            if rec["ok"]:
                f.write(f"[{rec['id']:>2}/{len(PROMPTS)}] {rec['elapsed_s']:>5}s  "
                        f"asset={rec['got_asset']!r:32.32} page={str(rec['got_page'])[-32:]:32.32} "
                        f"cards={rec['n_cards']} pay={rec['n_payload']} swap={rec['n_swapped']} "
                        f"pend={rec['asset_pending']} eps={rec['endpoints']}  :: {rec['prompt'][:54]}\n")
            else:
                f.write(f"[{rec['id']:>2}/{len(PROMPTS)}] ERROR {rec['error']}  :: {rec['prompt'][:54]}\n")
    return rec


def _summary(recs):
    ok = [r for r in recs if r.get("ok")]
    bad = [r for r in recs if not r.get("ok")]
    cols_hit = set()
    for r in ok:
        if r.get("n_payload"):
            cols_hit |= set(r.get("want_cols") or [])
    return {
        "total": len(recs), "ok": len(ok), "failed": len(bad),
        "classes_covered": sorted({r["want_klass"] for r in ok}),
        "intents_covered": sorted({r["want_intent"] for r in ok}),
        "pages_routed": sorted({str(r.get("got_page")) for r in ok if r.get("got_page")}),
        "assets_resolved": len({r.get("got_asset") for r in ok if r.get("got_asset")}),
        "metric_cols_hit": len(cols_hit),
        "asset_pending_count": sum(1 for r in ok if r.get("asset_pending")),
        "zero_card_count": sum(1 for r in ok if r.get("n_cards") == 0),
        "frame_fetched_count": sum(1 for r in ok if r.get("frames")),
        "avg_elapsed_s": round(sum(r.get("elapsed_s", 0) for r in ok) / max(1, len(ok)), 1),
        "failures": [{"id": r["id"], "prompt": r["prompt"], "error": r.get("error")} for r in bad],
    }


def main():
    open(RESULTS, "w").close()
    open(PROGRESS, "w").write(f"# batch start: {len(PROMPTS)} prompts, conc={CONC}, host={HOST}\n")
    recs = []
    with ThreadPoolExecutor(max_workers=CONC) as ex:
        futs = {ex.submit(_run_one, p): p for p in PROMPTS}
        for fut in as_completed(futs):
            recs.append(fut.result())
    recs.sort(key=lambda r: r["id"])
    s = _summary(recs)
    json.dump(s, open(SUMMARY, "w"), indent=1)
    with open(PROGRESS, "a") as f:
        f.write(f"\n# DONE  ok={s['ok']}/{s['total']} failed={s['failed']} "
                f"avg={s['avg_elapsed_s']}s pages={len(s['pages_routed'])} cols={s['metric_cols_hit']}\n")
    print(json.dumps(s, indent=1))


if __name__ == "__main__":
    main()
