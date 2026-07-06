#!/usr/bin/env bash
# tools/cert_fire18.sh — fire all 18 routable pages through the host in waves of 3 (<=3 page-concurrency; the per-page
# fan-out cap keeps each wave's vLLM load bounded). Dumps each response to /tmp/cert_<nn>.json and records the routed
# page_key + timing to /tmp/cert_routed.tsv for the verdict. Adopted config only (guided_json on, morphmap/prompt-v2 off).
set -u
OUT=/tmp/cert18; mkdir -p "$OUT"; : > /tmp/cert_routed.tsv
HOST=http://127.0.0.1:8770/api/run

# nn<TAB>prompt<TAB>expected_page_key
read -r -d '' PAGES <<'EOF'
01	real time monitoring for PCC Panel 1	panel-overview-shell/real-time-monitoring
02	energy and distribution for PCC Panel 1	panel-overview-shell/energy-distribution
03	energy and power for PCC Panel 1	panel-overview-shell/energy-power
04	harmonics and power quality for PCC Panel 1	panel-overview-shell/harmonics-pq
05	voltage and current for PCC Panel 1	panel-overview-shell/voltage-current
06	voltage and current for GIC-01-N3-UPS-01	individual-feeder-meter-shell/voltage-current
07	real time monitoring for GIC-01-N3-UPS-01	individual-feeder-meter-shell/real-time-monitoring
08	energy and power for GIC-01-N3-UPS-01	individual-feeder-meter-shell/energy-power
09	power quality for GIC-01-N3-UPS-01	individual-feeder-meter-shell/power-quality
10	dg voltage and current for DG-1	diesel-generator-asset-dashboard/voltage-current
11	dg engine and cooling for DG-1	diesel-generator-asset-dashboard/engine-cooling
12	dg fuel efficiency for DG-1	diesel-generator-asset-dashboard/fuel-efficiency
13	dg operations and runtime for DG-1	diesel-generator-asset-dashboard/operations-runtime
14	transformer tap and rtcc for Transformer-01	transformer-asset-dashboard/tap-rtcc
15	transformer thermal life for Transformer-01	transformer-asset-dashboard/thermal-life
16	ups battery and autonomy for GIC-01-N3-UPS-01	ups-asset-dashboard/battery-autonomy
17	ups output load capacity for GIC-01-N3-UPS-01	ups-asset-dashboard/output-load-capacity
18	ups source transfer for GIC-01-N3-UPS-01	ups-asset-dashboard/source-transfer
EOF

fire() {  # nn prompt expected
  local nn="$1" prompt="$2" expected="$3"
  local body t0 t1 code routed
  body=$(python3 -c "import json,sys;print(json.dumps({'prompt':sys.argv[1]}))" "$prompt")
  t0=$(python3 -c "import time;print(time.time())")
  code=$(curl -s -m 320 -X POST "$HOST" -H 'Content-Type: application/json' -d "$body" -o "$OUT/cert_$nn.json" -w '%{http_code}')
  t1=$(python3 -c "import time;print(time.time())")
  routed=$(python3 -c "import json;print((json.load(open('$OUT/cert_$nn.json')).get('page_key')) or '?')" 2>/dev/null || echo LOADFAIL)
  local ok="MISROUTE"; [ "$routed" = "$expected" ] && ok="ok"
  printf '%s\t%s\t%s\t%s\t%s\t%ss\t%s\n' "$nn" "$prompt" "$expected" "$routed" "$ok" \
     "$(python3 -c "print(round($t1-$t0))")" "$code" >> /tmp/cert_routed.tsv
  echo "  [$nn] HTTP $code routed=$routed $ok"
}

nns=(); prompts=(); exps=()
while IFS=$'\t' read -r nn prompt exp; do
  [ -z "$nn" ] && continue
  nns+=("$nn"); prompts+=("$prompt"); exps+=("$exp")
done <<< "$PAGES"

N=${#nns[@]}
for ((i=0; i<N; i+=3)); do
  echo "=== WAVE $((i/3+1)): pages ${nns[$i]:-} ${nns[$((i+1))]:-} ${nns[$((i+2))]:-} ==="
  for j in 0 1 2; do
    k=$((i+j)); [ $k -ge $N ] && break
    fire "${nns[$k]}" "${prompts[$k]}" "${exps[$k]}" &
  done
  wait
done
echo "=== CERT FIRE DONE ==="
echo "routed summary:"; column -t -s $'\t' /tmp/cert_routed.tsv | cut -c1-120
