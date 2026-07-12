#!/usr/bin/env bash
# tools/stack_monitor.sh — keep-alive + status monitor for the V48 acceptance campaign.
# Runs DETACHED (setsid) and survives across turns. Every INTERVAL it: (a) restarts any DEAD owned service with the
# ADOPTED config, (b) logs stack health + campaign progress to outputs/logs/stack_monitor.log (tail it anytime).
# Owned services it keeps alive: host :8770, frontend :5188. legacy EMS media :8890 RETIRED 2026-07-12 (GLBs are
# served by the web origin from host/web/public/media). External (vLLM :8200, neuract :5433)
# are health-logged only (not owned). Stop with: touch /tmp/stack_monitor.stop
set -u
ROOT=/home/rohith/desktop/BFI/backend/layer2/pipeline_v48
LOG=$ROOT/outputs/logs/stack_monitor.log
INTERVAL=60
ts() { date '+%F %T'; }
up() { ss -ltn 2>/dev/null | grep -q ":$1 "; }
ext_up() { timeout 4 bash -c "echo > /dev/tcp/127.0.0.1/$1" 2>/dev/null; }

start_host() { setsid bash -c "cd $ROOT && exec python3 host/server.py" > $ROOT/outputs/logs/host_stdout.log 2>&1 < /dev/null & disown; }
start_front() { setsid bash -c "cd $ROOT/host/web && exec npm run dev" > $ROOT/outputs/logs/frontend.log 2>&1 < /dev/null & disown; }

echo "[$(ts)] stack_monitor START (interval ${INTERVAL}s)" >> "$LOG"
while [ ! -f /tmp/stack_monitor.stop ]; do
  status=""
  if up 8770; then status+="host:UP "; else status+="host:DOWN->restart "; start_host; fi
  if up 5188; then status+="fe:UP ";   else status+="fe:DOWN->restart ";   start_front; fi
  ext_up 8200 && status+="vllm:UP " || status+="vllm:DOWN "
  ext_up 5433 && status+="neuract:UP " || status+="neuract:DOWN "
  cert=$(ls /tmp/cert18/cert_*.json 2>/dev/null | wc -l)
  camp=$(ls /tmp/campaign/*.json 2>/dev/null | wc -l)
  echo "[$(ts)] $status| cert18_dumps=$cert campaign_dumps=$camp" >> "$LOG"
  # bounded sleep that still checks the stop-flag
  for _ in $(seq 1 $INTERVAL); do [ -f /tmp/stack_monitor.stop ] && break; sleep 1; done
done
echo "[$(ts)] stack_monitor STOP (sentinel)" >> "$LOG"
