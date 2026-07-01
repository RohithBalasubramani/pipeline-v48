"""Per-asset ANSWERABLE metrics via the v48 validation layer (build-time).

Runs the pipeline's OWN non-AI validator in a subprocess (cwd = pipeline_v48, so the pipeline's
config/data packages resolve — the copilot's config.py/db.py would otherwise shadow them):
  col_dict(table)                  -> the asset's real consumer columns (label/kind/unit)
  validate.data_load.load_asset_frame -> recent rows into pandas (live neuract, :5433 tunnel)
  validate.data_validate.validate_data -> per-column pass / warn / fail (present? null-rate? recency?)
We keep the pass/warn columns = the metrics the data layer can ACTUALLY fill for that asset. The
copilot then only grounds the AI in these, so every suggested asset+metric pair is answerable
downstream. Fail-open: returns {} if the tunnel/validator is unavailable (the build still works,
the answerable-gate just stays off).
"""
import json
import os
import subprocess
import sys

_CODE = """
import json, os, sys
os.environ.setdefault('V48_VALIDATE_ROWS', sys.argv[2])
from layer1b.basket.col_dict import col_dict
from validate.data_load import load_asset_frame
from validate.data_validate import validate_data
out = {}
for t in json.loads(sys.argv[1]):
    basket = [{'column': c[0], 'label': c[1], 'kind': c[2], 'unit': c[3]} for c in col_dict(t)]
    if not basket:
        continue
    df, _loaded = load_asset_frame(t, [b['column'] for b in basket])
    rep = validate_data(df, basket)
    out[t] = [c['column'] for c in rep['columns'] if c['verdict'] in ('pass', 'warn')]
print(json.dumps(out))
"""


def validated_metrics(tables, rows=150, timeout=900):
    """{table: [validated column names]} for the given asset tables, via the v48 validation layer."""
    tables = [t for t in tables if t]
    if not tables:
        return {}
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # pipeline_v48
    try:
        proc = subprocess.run([sys.executable, "-c", _CODE, json.dumps(tables), str(rows)],
                              cwd=root, capture_output=True, text=True, timeout=timeout)
        if proc.returncode == 0 and proc.stdout.strip():
            return json.loads(proc.stdout.strip().splitlines()[-1])
        print(f"  [validated] validation layer failed (rc={proc.returncode}): {proc.stderr.strip()[:200]}")
    except Exception as e:
        print(f"  [validated] error: {str(e)[:140]}")
    return {}
