"""obs/stage.py — END-TO-END pipeline stage log. Each call prints `[<run_id>] <stage>: <fields>` to stderr (so it lands
in the host log — `tail -f outputs/host.log`) AND appends outputs/logs/pipeline_<run_id>.jsonl (replayable). Lets you
watch a single prompt's whole backend flow: 1a → 1b → validate → asset-gate → Layer 2 (per card) → fill → frames."""
import json
import os
import sys
import time

_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs", "logs")


def stage(run_id, name, **fields):
    parts = "  ".join(f"{k}={v}" for k, v in fields.items())
    print(f"  [{run_id}] {name:<11} {parts}", file=sys.stderr, flush=True)
    try:
        os.makedirs(_DIR, exist_ok=True)
        with open(os.path.join(_DIR, f"pipeline_{run_id}.jsonl"), "a") as f:
            f.write(json.dumps({"ts": time.time(), "stage": name, **fields}) + "\n")
    except Exception:
        pass
