#!/usr/bin/env bash
# tools/campaign_fire_extras.sh — the NON-18-page acceptance families, fired sequentially against the host:
#   CROSS  — 9 cross-class / edge prompts (homonym pins, dead meters, class routing) [sweep-harness CROSS set]
#   MULTI  — multi-asset compare lanes: pinned pair, pinned trio, natural compare prompt (picker expected)
#   KNOW   — knowledge pre-route: concept Q, off-domain refusal, asset prompt passthrough, follow-up history
# Dumps to /tmp/campaign/<family>_<nn>.json + a run manifest. Sequential = zero vLLM contention.
set -u
OUT=/tmp/campaign; mkdir -p "$OUT"; : > "$OUT/manifest.tsv"
H=http://127.0.0.1:8770/api/run

fire() { # family nn json_body note
  local fam="$1" nn="$2" body="$3" note="$4"
  local code t0 t1
  t0=$(date +%s)
  code=$(curl -s -m 320 -X POST "$H" -H 'Content-Type: application/json' -d "$body" -o "$OUT/${fam}_${nn}.json" -w '%{http_code}')
  t1=$(date +%s)
  printf '%s\t%s\t%s\t%s\t%ss\t%s\n' "$fam" "$nn" "$code" "$note" "$((t1-t0))" "$body" >> "$OUT/manifest.tsv"
  echo "  [$fam $nn] HTTP $code (${note})"
}
P() { python3 -c "import json,sys;print(json.dumps({'prompt':sys.argv[1]}))" "$1"; }

echo "=== CROSS-CLASS / EDGE (9) ==="
i=0
while IFS= read -r p; do
  i=$((i+1)); fire cross "$(printf '%02d' $i)" "$(P "$p")" "$p"
done <<'EOF'
Real-time power of DG-03 Jackson
Load profile of UPS-04 over the last 24 hours
UPS-01 load percentage right now
Show voltage levels for Transformer-03
Show voltage for UPS-10
real-time power and current for Transformer 01
energy consumption of Transformer-05 today
power quality for a spare feeder
voltage and current health for AHU-5
EOF

echo "=== MULTI-ASSET (3 lanes) ==="
fire multi 01 "$(python3 -c "import json;print(json.dumps({'prompt':'compare energy and power of UPS-01 and UPS-04','asset_ids':[11,23]}))")" "pinned pair 11+23"
fire multi 02 "$(python3 -c "import json;print(json.dumps({'prompt':'compare load of UPS-01, UPS-04 and BPDB-01','asset_ids':[11,23,16]}))")" "pinned trio 11+23+16"
fire multi 03 "$(P 'compare energy and power of GIC-01-N3-UPS-01 and GIC-02-N5-UPS-04')" "natural compare, no pins"

echo "=== KNOWLEDGE (4 routing cases) ==="
fire know 01 "$(P 'what is total harmonic distortion and why does it matter')" "concept Q -> knowledge"
fire know 02 "$(P 'what is the capital of France')" "off-domain -> refusal"
fire know 03 "$(P 'power quality for GIC-01-N3-UPS-01')" "asset prompt -> card pipeline"
fire know 04 "$(P 'explain what a power factor of 0.8 means for my plant')" "concept+plant -> knowledge"

echo "=== EXTRAS FIRE COMPLETE ==="
column -t -s $'\t' "$OUT/manifest.tsv" | cut -c1-150
