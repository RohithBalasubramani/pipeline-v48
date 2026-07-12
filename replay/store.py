"""replay/store.py — the bundle-on-disk concern: outputs/traces/<trace_id>/ layout, atomic-enough writes (one flush
at request end, never on the hot path), loads for the tape/compare side, listing + retention pruning."""
import json
import os
import shutil
import subprocess

from replay.ids import TRACES_DIR


def bundle_dir(trace_id):
    return os.path.join(TRACES_DIR, trace_id)


def _cfg(key, default):
    try:
        from config.app_config import cfg
        return cfg(key, default)
    except Exception:
        return default


def git_sha():
    try:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        out = subprocess.run(["git", "-C", root, "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=5)
        return out.stdout.strip() or None
    except Exception:
        return None


def write_bundle(trace_id, *, manifest, request, cfg_snapshot, env_snapshot, events, artifacts):
    """Persist one bundle. events = list of already-encoded dicts; artifacts = {name: json-safe obj}.
    Returns the bundle dir. Raises only upward into the fail-open capture wrapper."""
    d = bundle_dir(trace_id)
    os.makedirs(os.path.join(d, "artifacts"), exist_ok=True)
    with open(os.path.join(d, "events.jsonl"), "w") as f:
        for e in events:
            f.write(json.dumps(e, default=str) + "\n")
    for name, obj in (artifacts or {}).items():
        with open(os.path.join(d, "artifacts", f"{name}.json"), "w") as f:
            json.dump(obj, f, default=str)
    for name, obj in (("request", request), ("cfg_snapshot", cfg_snapshot),
                      ("env_snapshot", env_snapshot), ("manifest", manifest)):
        with open(os.path.join(d, f"{name}.json"), "w") as f:
            json.dump(obj, f, default=str, indent=1)
    _prune()
    return d


def load_bundle(d):
    """bundle dir → {manifest, request, cfg_snapshot, env_snapshot, events[], artifacts{name: obj}}."""
    out = {}
    for name in ("manifest", "request", "cfg_snapshot", "env_snapshot"):
        p = os.path.join(d, f"{name}.json")
        out[name] = json.load(open(p)) if os.path.exists(p) else None
    events = []
    ep = os.path.join(d, "events.jsonl")
    if os.path.exists(ep):
        with open(ep) as f:
            for line in f:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
    out["events"] = events
    arts = {}
    ad = os.path.join(d, "artifacts")
    if os.path.isdir(ad):
        for name in os.listdir(ad):
            if name.endswith(".json"):
                try:
                    arts[name[:-5]] = json.load(open(os.path.join(ad, name)))
                except Exception:
                    arts[name[:-5]] = None
    out["artifacts"] = arts
    out["dir"] = d
    return out


def _prune():
    """Keep the newest replay.keep_traces bundles (by manifest ts_start; unreadable ones oldest). Never raises;
    logs what was dropped (no silent cap)."""
    try:
        keep = int(_cfg("replay.keep_traces", 300) or 0)
        if keep <= 0:
            return
        from replay.ids import bundles_newest_first
        bundles = bundles_newest_first()
        for d, m in bundles[keep:]:
            shutil.rmtree(d, ignore_errors=True)
        if len(bundles) > keep:
            import sys
            sys.stderr.write(f"[replay] pruned {len(bundles) - keep} trace bundle(s) beyond replay.keep_traces={keep}\n")
    except Exception:
        pass
