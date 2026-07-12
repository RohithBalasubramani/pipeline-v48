"""tools/payload_diff — compare two pipeline executions across page / cards / metadata / bindings / SQL / validation /
renderer payload, with a terminal summary + a self-contained HTML report. Dev/observability tool, stdlib only, reads
the run artifacts the pipeline already persists (response_<rid>.json, pipeline_<rid>.jsonl, sql_<rid>.jsonl) or
captures a fresh execution via the host API. Every dimension degrades independently: a run missing one artifact still
diffs on all the others, with the reason stated. See README.md for the four comparison recipes."""
SNAPSHOT_VERSION = 1
