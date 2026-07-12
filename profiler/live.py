"""profiler/live.py — drive real prompts through the instrumented pipeline in-process.

Replicates host/server.py's do_POST order for a fresh prompt — knowledge gate first,
then build_response — with profiler.attach installed BEFORE any pipeline import, so
every span (stages + cross-cutting DB/AI) is recorded per prompt. Prompts run
SEQUENTIALLY: vLLM contention would pollute the numbers (the cert "llm timeout" was
contention, not a defect), so no page-level parallelism here.

Needs live services: vLLM :8200, cmd_catalog :5432, neuract :5433. Uses the same
DSN/config resolution as the real host server. Runs append to outputs/logs like any
real run — profiling runs ARE real runs.

Derived samples per run (recorded alongside raw spans):
  rendering = assembly_total − executor   (frame/payload assembly minus card fill)
  e2e       = knowledge gate + pipeline + assembly + response build, harness-timed
"""
import json
import os
import sys
import time
import uuid

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from profiler import attach, spans

# (tag, prompt, asset_id or None) — pinned ids avoid the asset picker so the full
# path runs; the 'ambiguous' and 'knowledge' rows exercise those early-exit paths.
CORPUS = [
    ("dg-voltage",        "dg voltage and current for DG-1", 2),
    ("dg-cooling",        "dg engine and cooling for DG-1", 2),
    ("dg-fuel",           "dg fuel efficiency for DG-1", 2),
    ("dg-runtime",        "dg operations and runtime for DG-1", 2),
    ("tx-tap",            "transformer tap and rtcc for Transformer-01", 171),
    ("tx-thermal",        "transformer thermal life for Transformer-01", 171),
    ("ups-battery",       "ups battery and autonomy for GIC-01-N3-UPS-01", 11),
    ("ups-load",          "ups output load capacity for GIC-01-N3-UPS-01", 11),
    ("ups-transfer",      "ups source transfer for GIC-01-N3-UPS-01", 11),
    ("panel-power",       "power overview for PCC-Panel-1", 318),
    ("panel-energy",      "energy consumption for PCC-Panel-2 last 7 days", 319),
    ("knowledge",         "what is power factor and why does it matter?", None),
    ("ambiguous",         "voltage for PCC Panel 1", None),
]


def _derive(samples):
    """Per-run derived spans from the raw ones (see module docstring)."""
    total = {s["stage"]: 0.0 for s in samples}
    for s in samples:
        total[s["stage"]] = total.get(s["stage"], 0.0) + s["ms"]
    out = []
    if "assembly_total" in total and "executor" in total:
        ms = total["assembly_total"] - total["executor"]
        if ms >= 0:
            out.append({"stage": "rendering", "ms": ms, "source": "live",
                        "meta": {"note": "assembly_total - executor"}})
    return out


def run(out_path):
    server = attach.install()
    attach.verify(server)
    from knowledge.ems import ask as ems_ask   # binds the wrapper (installed above)

    all_samples, failures = [], []
    for i, (tag, prompt, asset_id) in enumerate(CORPUS, 1):
        label = f"live_{tag}_{uuid.uuid4().hex[:6]}"
        print(f"[{i}/{len(CORPUS)}] {tag}: {prompt!r} (asset_id={asset_id})", flush=True)
        with spans.session(label, prompt) as sess:
            t0 = time.perf_counter()
            try:
                kind = None
                if asset_id is None:
                    k = ems_ask(prompt, None)
                    kind = k.get("kind")
                if kind in ("knowledge", "off_scope"):
                    resp_note = {"kind": kind}
                else:
                    resp = server.build_response(prompt, asset_id=asset_id)
                    resp_note = {"kind": "dashboard", "cards": len(resp.get("cards") or []),
                                 "asset_pending": (resp.get("asset") or {}).get("pending") or resp.get("asset_pending")}
                e2e_ms = (time.perf_counter() - t0) * 1000.0
                sess.record("e2e", e2e_ms, tag=tag, **{k: v for k, v in resp_note.items() if v is not None})
                print(f"    -> {e2e_ms/1000:.1f}s {resp_note}", flush=True)
            except Exception as e:
                failures.append({"tag": tag, "prompt": prompt, "error": f"{type(e).__name__}: {e}"})
                print(f"    -> FAILED {type(e).__name__}: {e}", flush=True)
        for d in _derive(sess.samples):
            sess.samples.append({**d, "run_id": label, "prompt": prompt})
        all_samples.extend(sess.samples)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump({"samples": all_samples, "failures": failures,
                   "corpus": [{"tag": t, "prompt": p, "asset_id": a} for t, p, a in CORPUS]}, f)
    print(f"live profiling done: {len(all_samples)} samples, {len(failures)} failures -> {out_path}", flush=True)
    return all_samples, failures


if __name__ == "__main__":
    run(os.path.join(_ROOT, "outputs", "latency", "live_samples.json"))
