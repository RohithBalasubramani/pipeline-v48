"""outputs/batch/analyze.py — roll up results.jsonl into a COVERAGE + ANOMALY report.
Coverage: classes/intents/pages/assets/metric-cols actually exercised. Anomalies (flagged, not graded —
the page_hint was only a hint, the AI may legitimately pick feeder-vs-panel shell): asset-name mismatch,
class mismatch, zero-card, unfilled payload, off-domain endpoint vs intent, conformance fails, frame fails,
asset_pending, errors. Pulls per-card conforms/fail + frame ok from the per-run logs (last run per run_id)."""
import collections
import glob
import json
import os

HERE = os.path.dirname(__file__)
RESULTS = os.path.join(HERE, os.environ.get("BATCH_RESULTS", "results.jsonl"))
ANALYSIS_OUT = os.path.join(HERE, os.environ.get("BATCH_ANALYSIS_OUT", "analysis.json"))
LOGDIR = os.path.join(HERE, "..", "logs")

# the ems_backend endpoint family each INTENT should land in (off-family = flagged)
INTENT_DOMAIN = {
    "realtime": {"real-time-monitoring"}, "frequency": {"real-time-monitoring"},
    "energy-power": {"energy-power", "energy-power-history", "demand-profile"},
    "energy-kwh": {"energy-power", "energy-power-history"}, "demand": {"demand-profile", "energy-power-history"},
    "reactive": {"energy-power"}, "apparent": {"energy-power"}, "perphase-pwr": {"energy-power"},
    "powerfactor": {"energy-power", "power-quality"}, "compare": {"energy-power", "voltage-current"},
    "distribution": {"energy-distribution"},
    "voltage": {"voltage-current"}, "voltage-ll": {"voltage-current"}, "current": {"voltage-current"},
    "unbalance": {"voltage-current"},
    "voltage-hist": {"voltage-history", "voltage-current"}, "current-hist": {"current-history", "voltage-current"},
    "harmonics": {"harmonics-pq", "power-quality", "power-quality-history", "distortion-harmonics"},
    "current-thd": {"harmonics-pq", "power-quality", "distortion-harmonics"},
    "pq-summary": {"power-quality", "harmonics-pq", "power-quality-history"},
    "anomaly": {"load-anomalies", "energy-power"}, "overview-sld": {"overview", "real-time-monitoring", "energy-power"},
}


def load_results():
    return [json.loads(l) for l in open(RESULTS) if l.strip()]


def card_detail(run_id):
    """last RESPONSE-bounded pass for this run_id → per-card conforms/fail + frame oks."""
    f = os.path.join(LOGDIR, f"pipeline_{run_id}.jsonl")
    if not os.path.exists(f):
        return None
    cards, frames = {}, {}
    for line in open(f):
        try:
            d = json.loads(line)
        except Exception:
            continue
        if d.get("stage") == "PROMPT":          # new pass → reset (keep LAST pass only)
            cards, frames = {}, {}
        elif d.get("stage") == "L2.card":
            cards[d.get("id")] = {"conforms": d.get("conforms"), "fail": d.get("fail"),
                                  "endpoint": d.get("endpoint"), "swap": d.get("swap")}
        elif d.get("stage") == "frame":
            frames[d.get("endpoint")] = d.get("ok")
    return {"cards": cards, "frames": frames}


def main():
    recs = load_results()
    ok = [r for r in recs if r.get("ok")]
    bad = [r for r in recs if not r.get("ok")]

    cov = {
        "total": len(recs), "ok": len(ok), "failed": len(bad),
        "classes": sorted({r["want_klass"] for r in ok}),
        "intents": sorted({r["want_intent"] for r in ok}),
        "pages_routed": sorted({r.get("got_page") for r in ok if r.get("got_page")}),
        "assets_resolved": sorted({r.get("got_asset") for r in ok if r.get("got_asset")}),
        "metric_cols_hit": sorted({c for r in ok if r.get("n_payload") for c in r.get("want_cols", [])}),
    }

    anomalies = collections.defaultdict(list)
    for r in ok:
        rid = r["id"]
        if r.get("got_asset") and r["got_asset"].strip().lower() != r["want_asset"].strip().lower():
            anomalies["asset_name_mismatch"].append((rid, r["prompt"], f"want={r['want_asset']} got={r['got_asset']}"))
        if r.get("asset_pending"):
            anomalies["asset_pending"].append((rid, r["prompt"], f"cands={r.get('n_candidates')}"))
        if r.get("n_cards", 0) == 0:
            anomalies["zero_cards"].append((rid, r["prompt"], r.get("got_page")))
        elif r.get("n_payload", 0) < r.get("n_cards", 0):
            anomalies["unfilled_payload"].append((rid, r["prompt"], f"{r['n_payload']}/{r['n_cards']}"))
        # off-domain endpoint vs intent
        want_dom = INTENT_DOMAIN.get(r["want_intent"])
        if want_dom:
            stray = [e for e in (r.get("endpoints") or []) if e not in want_dom]
            if stray and not (set(r.get("endpoints") or []) & want_dom):
                anomalies["off_domain_endpoint"].append((rid, r["prompt"], f"want~{sorted(want_dom)} got={r.get('endpoints')}"))
        # deep: conformance + frame from logs
        det = card_detail(r.get("run_id"))
        if det:
            nfail = sum(1 for c in det["cards"].values() if c.get("conforms") is False)
            if nfail:
                anomalies["conformance_fail"].append((rid, r["prompt"], f"{nfail}/{len(det['cards'])} cards non-conforming"))
            badframe = [e for e, okk in det["frames"].items() if okk is False]
            if badframe:
                anomalies["frame_fail"].append((rid, r["prompt"], f"frames not ok: {badframe}"))

    print("=" * 70, "\nCOVERAGE\n", "=" * 70, sep="")
    print(json.dumps(cov, indent=1))
    print(f"\nclasses={len(cov['classes'])}/7  intents={len(cov['intents'])}/22  "
          f"pages_routed={len(cov['pages_routed'])}  assets={len(cov['assets_resolved'])}  "
          f"metric_cols={len(cov['metric_cols_hit'])}/41")

    print("\n", "=" * 70, "\nANOMALIES (flagged for review — not all are bugs)\n", "=" * 70, sep="")
    for cat, items in sorted(anomalies.items(), key=lambda kv: -len(kv[1])):
        print(f"\n## {cat}  ({len(items)})")
        for rid, prompt, note in items[:40]:
            print(f"  [{rid:>2}] {note}   :: {prompt[:60]}")
    if bad:
        print(f"\n## hard_failures ({len(bad)})")
        for r in bad:
            print(f"  [{r['id']:>2}] {r.get('error')}   :: {r['prompt'][:60]}")

    json.dump({"coverage": cov, "anomalies": {k: v for k, v in anomalies.items()}},
              open(ANALYSIS_OUT, "w"), indent=1)


if __name__ == "__main__":
    main()
