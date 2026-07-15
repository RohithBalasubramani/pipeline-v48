"""admin/explorer.py — pipeline explorer: the stage graph with aggregate health + page/asset drill-downs.

The pipeline's shape is FIXED (PROMPT → 1a ∥ 1b → validate → asset_gate → layer2/L2.card → reflect → exec →
RESPONSE); this report populates each node with how the fleet of runs in the window actually behaved there:
touches, event counts, avg spacing, failures attributed by the failures sink's stage field, sample runs."""
from admin import failures_report, runs, store
from admin.config import STAGE_ORDER, in_window

# failures_*.jsonl stage values → the graph node they belong to (best-effort; unknown stages → 'other').
# stage==failures_report.BLANK_STAGE ("reason") rows are per-leaf honest-blank telemetry, not failures — they are
# skipped in report() below (same classification rule as failures_report.report), never attributed to a node.
_FAIL_NODE = {"llm": "layer2", "L2.card": "L2.card", "exec": "exec",
              "1a": "1a", "layer1a": "1a", "1b": "1b", "layer1b": "1b",
              "validate": "validate", "validation": "validate",
              "preflight_reroute": "preflight_reroute", "notes": "notes",
              "layer2": "layer2", "reflect": "reflect", "harness": "layer2"}

# pipeline_*.jsonl stage values → graph node, for the EVENTS side (mirrors _FAIL_NODE: 1b span ERROR mirrors log
# themselves as 'layer1b' — without this alias those events were invisible while their failures counted under 1b).
_EVENT_NODE = {"layer1a": "1a", "layer1b": "1b"}


def report(t_from=None, t_to=None):
    nodes = {s: {"stage": s, "runs": 0, "events": 0, "failures": 0, "sample_runs": []} for s in STAGE_ORDER}
    other_fail = 0
    pages, assets = {}, {}
    for rid in store.run_ids():
        ts = store.last_ts(rid)
        if not in_window(ts, t_from, t_to):
            continue
        seen = set()
        for sl in runs.executions(rid):
            for rec in sl:
                s = rec.get("stage")
                s = _EVENT_NODE.get(s, s)
                if s not in nodes:
                    continue
                nodes[s]["events"] += 1
                if s not in seen:
                    seen.add(s)
                    nodes[s]["runs"] += 1
                    if len(nodes[s]["sample_runs"]) < 5:
                        nodes[s]["sample_runs"].append(rid)
        for f in failures_report._rows(rid):
            if failures_report.classify(f) != "real":          # ONE classification home — blanks, honest gaps,
                continue                                       # write-twins and pytest artifacts never count as failures
            if not in_window(f["ts_epoch"], t_from, t_to):
                continue
            node = _FAIL_NODE.get(f["stage"])
            if node in nodes:
                nodes[node]["failures"] += 1
            else:
                other_fail += 1
        s = runs.summary(rid)
        if s.get("page_key"):
            p = pages.setdefault(s["page_key"], {"page_key": s["page_key"], "runs": 0, "cards": 0,
                                                 "elapsed": [], "run_ids": []})
            p["runs"] += 1
            p["cards"] += s.get("cards") or 0
            if s.get("elapsed_ms"):
                p["elapsed"].append(s["elapsed_ms"])
            if len(p["run_ids"]) < 8:
                p["run_ids"].append(rid)
        if s.get("asset"):
            a = assets.setdefault(s["asset"], {"asset": s["asset"], "asset_class": s.get("asset_class"),
                                               "runs": 0, "run_ids": []})
            a["runs"] += 1
            if len(a["run_ids"]) < 8:
                a["run_ids"].append(rid)
    page_rows = []
    for p in pages.values():
        avg = int(sum(p["elapsed"]) / len(p["elapsed"])) if p["elapsed"] else None
        page_rows.append({"page_key": p["page_key"], "runs": p["runs"], "cards": p["cards"],
                          "avg_elapsed_ms": avg, "run_ids": p["run_ids"]})
    page_rows.sort(key=lambda p: -p["runs"])
    asset_rows = sorted(assets.values(), key=lambda a: -a["runs"])
    return {
        "stages": [nodes[s] for s in STAGE_ORDER if nodes[s]["events"] or nodes[s]["runs"] or nodes[s]["failures"]],
        "other_failures": other_fail,
        "pages": page_rows,
        "assets": asset_rows[:40],
        "assets_total": len(asset_rows),   # the [:40] cap can truncate — lets the UI say "40 of N"
    }
