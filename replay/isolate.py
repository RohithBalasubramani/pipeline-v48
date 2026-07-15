"""replay/isolate.py — keep a replay from clobbering the original run's legacy artifacts. A replayed prompt hashes
to the SAME run_id (run/run_id.py is a prompt hash), so without redirection the replay would APPEND to the original
ai_<rid>.jsonl / pipeline_<rid>.jsonl / sql_<rid>.jsonl and OVERWRITE response_<rid>.json + notes. Redirection now
rides obs/paths.set_override — the ONE writer-dir door every legacy writer (incl. host._dump_response) resolves per
call — so one override covers all of them (the old per-module _OUT/_DIR pokes went inert when the writers moved to
the door). Engine-only; never used on the live serving path."""
import os


def redirect_legacy_writers(bundle_dir):
    d = os.path.join(bundle_dir, "legacy_logs")
    os.makedirs(d, exist_ok=True)
    from obs import paths
    paths.set_override(d)                               # logs + notes both land in the bundle (historical behavior)
    return d
