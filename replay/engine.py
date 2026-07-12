"""replay/engine.py — re-execute a recorded request. ORDER MATTERS (imports bake config):
env snapshot → cfg pin (pre-seed config.app_config BEFORE the pipeline imports) → clock freeze → legacy-writer
isolation (import host.server only now) → tape install → re-run the SAME entry (host.server.handle_run/handle_frame)
under obs middleware + capture → compare against the original → report. Always run in a FRESH process (the CLI does);
never import this on the serving path."""
import os
import sys
import uuid

from replay import ids, store
from replay.capture import ENV_PREFIXES
from replay.tape import Tape

MODES = {"pinned": ("llm", "sql", "frame", "insight", "cfg"), "live": ()}


def replay(trace_ref, *, mode="pinned", pins=None, strict=False):
    """Returns (replay_bundle_dir, comparison dict). mode: 'pinned' | 'live'; pins overrides the mode's pin set
    (any of llm,sql,frame,insight,cfg)."""
    orig_dir, manifest = ids.resolve(trace_ref)
    bundle = store.load_bundle(orig_dir)
    if manifest.get("kind") == "frame":
        path, handler_name = "/api/frame", "handle_frame"
    else:
        path, handler_name = "/api/run", "handle_run"
    body = ((bundle.get("request") or {}).get("body")) or {}
    pin_set = set(pins) if pins is not None else set(MODES.get(mode, MODES["pinned"]))

    _apply_env(bundle.get("env_snapshot") or {})
    if "cfg" in pin_set:
        _pin_cfg(bundle.get("cfg_snapshot") or {})
    from replay import clock
    t0 = manifest.get("started_at_iso")
    if t0:
        clock.freeze(t0)

    replay_trace_id = f"t_{uuid.uuid4().hex}"
    rdir = store.bundle_dir(replay_trace_id)
    os.makedirs(rdir, exist_ok=True)
    from replay.isolate import redirect_legacy_writers          # imports host.server → the whole pipeline (post-pin)
    redirect_legacy_writers(rdir)

    tape = Tape(bundle.get("events") or [], pins=(pin_set - {"cfg"}), strict=strict)
    import host.server as server
    handler = getattr(server, handler_name)

    from obs.middleware import run_traced
    from replay.capture import captured

    def _run():
        code, resp = handler(dict(body))
        return resp

    resp = run_traced("replay", {"prompt": body.get("prompt"), "asset_id": body.get("asset_id")},
                      lambda: captured("replay", body, _run, tape=tape, replay_of=manifest["trace_id"],
                                       mode=mode, path=path, trace_id=replay_trace_id))
    # leftover ORIGINAL LLM calls the replay never made are a divergence signal — persist beside the comparison
    unconsumed = [{"stage": e.get("stage"), "seq": e.get("seq")} for e in tape.unconsumed_llm()]

    from replay.compare import compare_bundles
    replay_bundle = store.load_bundle(rdir)
    comparison = compare_bundles(bundle, replay_bundle)
    comparison["tape"] = {"stats": tape.stats, "unconsumed_llm": unconsumed,
                          "pins": sorted(pin_set), "strict": strict, "mode": mode}
    _write_reports(rdir, comparison)
    return rdir, comparison


def _write_reports(rdir, comparison):
    import json
    d = os.path.join(rdir, "replay")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "comparison.json"), "w") as f:
        json.dump(comparison, f, default=str, indent=1)
    try:
        from replay.report import render_html
        with open(os.path.join(d, "report.html"), "w") as f:
            f.write(render_html(comparison))
    except Exception as e:
        sys.stderr.write(f"[replay] html report failed (comparison.json intact): {type(e).__name__}: {e}\n")


def _apply_env(snapshot):
    """Reproduce the recorded environment for the replay-relevant prefixes: set recorded values, DROP vars that did
    not exist at record time (an env var added since would silently change routing/pinning). Redacted (credential)
    entries keep the CURRENT process value — secrets are never persisted in a bundle."""
    from replay.capture import ENV_REDACTED
    for k in list(os.environ):
        if k.startswith(ENV_PREFIXES) and k not in snapshot:
            del os.environ[k]
    os.environ.update({k: str(v) for k, v in snapshot.items() if v != ENV_REDACTED})


def _pin_cfg(snapshot):
    """Pre-seed config.app_config with the recorded rows — MUST run before any pipeline module import (several bake
    cfg() values at import). Replacing _load keeps cfg()'s casting/fallback behavior byte-identical."""
    import config.app_config as app_config
    frozen = {k: tuple(v) for k, v in snapshot.items()}
    app_config._load = lambda: frozen
