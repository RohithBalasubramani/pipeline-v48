"""outputs/batch/compare_runs.py — diff the pre-fix run (analysis.json) vs the post-fix re-run (analysis_v2.json).
Shows coverage parity + the per-cluster anomaly delta, so the effect of the endpoint/offer-list/fetch_frame/host
fixes is visible. Run 1 = frozen pre-fix baseline; Run 2 = after the audit fixes + host restart."""
import collections
import json
import os

HERE = os.path.dirname(__file__)
a1 = json.load(open(os.path.join(HERE, "analysis.json")))
a2 = json.load(open(os.path.join(HERE, "analysis_v2.json")))

CLUSTERS = ["frame_fail", "conformance_fail", "off_domain_endpoint", "asset_name_mismatch",
            "zero_cards", "unfilled_payload"]


def counts(a):
    an = a.get("anomalies", {})
    return {c: len(an.get(c, [])) for c in CLUSTERS}


def frame_fail_breakdown(a):
    """split frame_fail by endpoint family so we see PQ (fixed) vs DG (unfixed) separately."""
    bd = collections.Counter()
    for _id, _prompt, note in a.get("anomalies", {}).get("frame_fail", []):
        for ep in ("power-quality-history", "distortion-harmonics", "voltage-history", "current-history",
                   "voltage-current", "energy-distribution", "energy-power-history", "power-quality-summary"):
            if ep in note:
                bd[ep] += 1
    return dict(bd)


c1, c2 = counts(a1), counts(a2)
cov1, cov2 = a1["coverage"], a2["coverage"]

print("=" * 72)
print("COVERAGE PARITY (both runs cover the same scenario space)")
print("=" * 72)
for k in ("ok", "failed"):
    print(f"  {k:10} run1={cov1.get(k)}   run2={cov2.get(k)}")
for k in ("classes", "intents", "pages_routed", "assets_resolved", "metric_cols_hit"):
    print(f"  {k:16} run1={len(cov1.get(k, []))}   run2={len(cov2.get(k, []))}")

print("\n" + "=" * 72)
print("ANOMALY DELTA  (run1 = pre-fix  ->  run2 = post-fix)")
print("=" * 72)
print(f"  {'cluster':22} {'run1':>5} {'run2':>5} {'Δ':>6}")
for c in CLUSTERS:
    d = c2[c] - c1[c]
    arrow = "  ✓ improved" if d < 0 else ("  (same)" if d == 0 else "  ⚠ worse")
    print(f"  {c:22} {c1[c]:>5} {c2[c]:>5} {d:>+6}{arrow}")

print("\n  frame_fail by endpoint family:")
b1, b2 = frame_fail_breakdown(a1), frame_fail_breakdown(a2)
for ep in sorted(set(b1) | set(b2)):
    print(f"    {ep:24} run1={b1.get(ep,0):>3}  run2={b2.get(ep,0):>3}")

# the remaining frame_fails in run2: are they ALL diesel-generator (the known unfixed backend gap)?
remaining = a2.get("anomalies", {}).get("frame_fail", [])
dg = [r for r in remaining if "iesel" in r[1] or "DG " in r[1]]
print(f"\n  run2 frame_fails: {len(remaining)} total | {len(dg)} are Diesel-Generator (known unfixed dg-strategy gap)")
print(f"  non-DG frame_fails remaining in run2: {len(remaining) - len(dg)}")
for r in remaining:
    if r not in dg:
        print(f"    [{r[0]}] {r[2]}  :: {r[1][:54]}")
