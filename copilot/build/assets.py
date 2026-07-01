"""Authoritative asset list for the suggestion corpus.

The v48 pipeline resolver (layer1b/resolve/asset_candidates.py) is the source of truth:
the meta_data_version1 device registry joined to the LIVE neuract data tables. It is run
in its OWN process (cwd = pipeline_v48) so the pipeline's config/data packages resolve
cleanly — the copilot's own config.py/db.py would otherwise shadow them — keeping the
copilot runtime at zero import-coupling. Falls back to raw live neuract table names.
"""
import json
import os
import subprocess
import sys

import db
from config import DATA_DB, MAP_SCHEMA, MAP_TABLE

from .naming import _SKIP_ASSET, _asset_location, _fallback_asset_name


def _v48_assets():
    """Authoritative asset list from the v48 pipeline resolver
    (layer1b/resolve/asset_candidates.py — the meta_data_version1 device registry joined to the live
    neuract data tables). Run in its OWN process (cwd = pipeline_v48) so the pipeline's config/data
    packages resolve cleanly — the copilot's own config.py/db.py would otherwise shadow them — and so
    the copilot runtime keeps zero import-coupling. Returns dicts {name, table, load_group, class};
    falls back to the live neuract table names if the resolver is unavailable."""
    # pipeline_v48 = copilot/build/ -> copilot/ -> pipeline_v48/
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    code = ("import json; from layer1b.resolve.asset_candidates import asset_candidates; "
            "print(json.dumps(asset_candidates()))")
    try:
        proc = subprocess.run([sys.executable, "-c", code], cwd=root,
                              capture_output=True, text=True, timeout=120)
        if proc.returncode == 0 and proc.stdout.strip():
            rows = json.loads(proc.stdout.strip().splitlines()[-1])  # [id, name, table, type, load_group, class]
            res = [{"name": r[1], "table": r[2], "load_group": r[4] or "", "class": r[5] or ""}
                   for r in rows if r[2]]
            if res:
                return res
        print(f"  [assets] v48 resolver failed (rc={proc.returncode}): {proc.stderr.strip()[:200]}")
    except Exception as e:
        print(f"  [assets] v48 resolver error: {str(e)[:120]}")
    fb = []
    for (tbl,) in db.rows(DATA_DB, f"SELECT DISTINCT table_name FROM {MAP_SCHEMA}.{MAP_TABLE} "
                                    f"WHERE coalesce(table_name,'') <> '' ORDER BY table_name"):
        if _SKIP_ASSET.match(tbl):
            continue
        fb.append({"name": _fallback_asset_name(tbl), "table": tbl,
                   "load_group": _asset_location(tbl), "class": ""})
    return fb
