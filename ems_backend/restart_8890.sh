#!/usr/bin/env bash
# Reliable restart for the pipeline_v48 ems_backend on :8890.
# NOTE: `fuser -k 8890/tcp` does NOT see this socket→pid on this host, so it silently no-ops and the OLD
# (stale) code keeps serving. Match by cmdline with pkill -f instead, then relaunch from a clean module state.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
PY=/home/rohith/.pyenv/versions/3.11.9/bin/python3.11
echo "killing any daphne on :8890 (by cmdline)…"
pkill -9 -f "daphne .*-p 8890 backend.asgi" 2>/dev/null && sleep 2 || true
find "$HERE/lt_panels" -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true   # avoid stale .pyc
cd "$HERE"
DJANGO_SETTINGS_MODULE=backend.settings PYTHONPATH="$HERE" \
  nohup "$PY" -m daphne -b 0.0.0.0 -p 8890 backend.asgi:application > /home/rohith/.tmp/ems8890.log 2>&1 &
sleep 5
if ss -ltn 2>/dev/null | grep -q ":8890"; then echo "ems_backend :8890 up (pid $(pgrep -f 'daphne .*-p 8890'))"; else echo "FAILED — see /home/rohith/.tmp/ems8890.log"; tail -3 /home/rohith/.tmp/ems8890.log; fi
