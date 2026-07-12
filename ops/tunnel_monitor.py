"""ops/tunnel_monitor.py — watch the :5433 neuract tunnel and auto-re-run the asset sweep on recovery.

The tunnel is an SSH port-forward (127.0.0.1:5433 -> 10.90.200.91:5432) that flaps on link loss. This monitor polls
it with a REAL query (SELECT 1 through psql, not just a TCP accept — ssh accepts the socket even when the remote is
dead), logs every up/down transition, and on a DOWN->UP RECOVERY runs tools/asset_sweep.py so the domain-telemetry
cert is re-validated automatically the moment data is reachable again.

Bounded + interruptible: stops after MAX_HOURS or when outputs/.stop_tunnel_monitor exists. Logs to
outputs/tunnel_monitor.log. Run in background:  nohup python3 ops/tunnel_monitor.py &  (or the harness bg runner).

Env knobs: TUNNEL_MONITOR_INTERVAL (secs, default 90), TUNNEL_MONITOR_HOURS (default 6),
TUNNEL_MONITOR_SWEEP_ON_START (1 = also sweep on the first healthy poll, default 0).
"""
import os, sys, time, subprocess, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, "outputs", "tunnel_monitor.log")
STOP = os.path.join(ROOT, "outputs", ".stop_tunnel_monitor")
INTERVAL = int(os.environ.get("TUNNEL_MONITOR_INTERVAL", "90"))
MAX_HOURS = float(os.environ.get("TUNNEL_MONITOR_HOURS", "6"))
SWEEP_ON_START = os.environ.get("TUNNEL_MONITOR_SWEEP_ON_START", "0") == "1"


def log(msg):
    line = f"{datetime.datetime.now().isoformat(timespec='seconds')}  {msg}"
    print(line, flush=True)
    with open(LOG, "a") as fh:
        fh.write(line + "\n")


def tunnel_healthy():
    """True only if a REAL query returns through the tunnel (ssh accepts the socket even when the remote DB is dead).
    Target comes from config.databases.conn_env(DATA_DB) — the ONE DB-wiring home (config F7): relocate the data DB
    via PG_HOST/PG_PORT/PG_DB and the monitor follows instead of probing a :5433 socket nobody uses."""
    try:
        if ROOT not in sys.path:
            sys.path.insert(0, ROOT)
        from config.databases import conn_env, DATA_DB
        env = {**os.environ, **conn_env(DATA_DB), "PGCLIENTENCODING": "UTF8"}
        env["PGCONNECT_TIMEOUT"] = os.environ.get("PG_CONNECT_TIMEOUT", "8")   # keep this monitor's 8s connect leash
        r = subprocess.run(["psql", "-d", DATA_DB, "-tAc", "select 1"],
                           capture_output=True, text=True, timeout=15, env=env)
        return r.returncode == 0 and r.stdout.strip() == "1"
    except Exception:
        return False


def run_sweep(reason):
    log(f"RUN asset_sweep ({reason}) ...")
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "asset_sweep.py")],
                       capture_output=True, text=True, cwd=ROOT,
                       env={**os.environ, "PYTHONPATH": ROOT})
    tail = "\n".join((r.stdout or "").strip().splitlines()[-3:])
    log(f"asset_sweep exit={r.returncode}\n{tail}")


def main():
    log(f"tunnel_monitor START interval={INTERVAL}s max={MAX_HOURS}h sweep_on_start={SWEEP_ON_START}")
    deadline = time.time() + MAX_HOURS * 3600
    prev = None                                        # None=unknown, True=up, False=down
    while time.time() < deadline:
        if os.path.exists(STOP):
            log("stop file present — exiting"); os.remove(STOP); break
        up = tunnel_healthy()
        if up != prev:
            log(f"tunnel {'UP' if up else 'DOWN'}" + (" (was " + ("UP" if prev else "DOWN") + ")" if prev is not None else ""))
            if up and prev is False:                   # DOWN -> UP recovery
                run_sweep("tunnel recovered")
            elif up and prev is None and SWEEP_ON_START:
                run_sweep("first healthy poll")
            prev = up
        time.sleep(INTERVAL)
    log("tunnel_monitor EXIT (deadline or stop)")


if __name__ == "__main__":
    main()
