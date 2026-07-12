"""replay/isolate.py — keep a replay from clobbering the original run's legacy artifacts. A replayed prompt hashes
to the SAME run_id (run/run_id.py is a prompt hash), so without redirection the replay would APPEND to the original
ai_<rid>.jsonl / pipeline_<rid>.jsonl / sql_<rid>.jsonl and OVERWRITE response_<rid>.json + notes. This module
points every legacy writer's module-global output dir into <replay bundle>/legacy_logs/ — same precedent as the
writers themselves (module globals, set once). Engine-only; never used on the live serving path."""
import os


def redirect_legacy_writers(bundle_dir):
    d = os.path.join(bundle_dir, "legacy_logs")
    os.makedirs(d, exist_ok=True)
    import obs.ai_log as ai_log
    ai_log._OUT = d
    import obs.stage as stage
    stage._DIR = d
    try:
        import obs.sql_trace as sql_trace
        sql_trace._OUT = d
    except Exception:
        pass
    try:
        import obs.notes as notes
        for attr in ("_DIR", "_OUT"):
            if hasattr(notes, attr):
                setattr(notes, attr, d)
    except Exception:
        pass
    try:
        import obs.failures as failures
        for attr in ("_DIR", "_OUT"):
            if hasattr(failures, attr):
                setattr(failures, attr, d)
    except Exception:
        pass
    import host.server as server                                # response_<rid>.json dump → the bundle
    _orig_dump = server._dump_response

    def _dump_to_bundle(resp):
        try:
            import json
            rid = (resp or {}).get("run_id") or "default"
            with open(os.path.join(d, f"response_{rid}.json"), "w") as f:
                json.dump(resp, f, default=str)
        except Exception:
            pass
    server._dump_response = _dump_to_bundle
    return d
