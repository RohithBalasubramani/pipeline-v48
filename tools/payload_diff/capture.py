"""tools/payload_diff/capture.py — run ONE fresh execution through the live host API and snapshot it. One concern:
the HTTP call + the wire-copy → snapshot handoff (assembly itself is snapshot.build). The response is taken from the
wire, not from disk, so two back-to-back captures of the SAME prompt each keep their own response even though the host
overwrites response_<rid>.json. SQL slice = the trace records that landed between the request being sent and the
response arriving (the host executes fills inside that span)."""
import json
import time
import urllib.request

from tools.payload_diff import logs as L
from tools.payload_diff import snapshot as S

from config.endpoints import HOST_BASE as DEFAULT_HOST   # the ONE :8770 home (config F7; honors V48_HOST_API/V48_HOST_PORT)


def capture(prompt, asset_id=None, host=DEFAULT_HOST, label=None, timeout_s=600, date_window=None):
    """POST /api/run and return (snapshot, saved_path). Raises on transport errors — a capture the user asked for
    must not silently degrade to an empty snapshot."""
    body = {"prompt": prompt}
    if asset_id is not None:
        body["asset_id"] = asset_id
    if date_window is not None:
        body["date_window"] = date_window
    req = urllib.request.Request(f"{host.rstrip('/')}/api/run", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        response = json.loads(resp.read())
    t1 = time.time()

    run_id = response.get("run_id") or L.make_run_id(prompt)
    if response.get("kind") == "knowledge":
        raise SystemExit(f"prompt routed to the KNOWLEDGE layer (no cards to diff): {response.get('answer', '')[:200]}")

    # the fills ran inside [t0, t1]; slice the trace by that window rather than the stage segment (tighter, and
    # correct even when an earlier execution of the same prompt is still flushing records)
    sql = [r for r in L.sql_log(run_id)
           if isinstance(r.get("ts"), (int, float)) and t0 - 1 <= r["ts"] <= t1 + 1]

    snap = S.build(run_id, occurrence=-1, response=response, sql=sql, source="live",
                   label=label, prompt=prompt, asset_id=asset_id, host=host)
    return snap, S.save(snap)
