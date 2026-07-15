"""tests/test_registry_drift_live.py — LIVE registry↔information_schema drift gate (pytest -m live).

Pins the permanence contract from the 2026-07-14 failures audit (01 F1): every neuract.lt_mfm row whose
physical table is missing must be MARKED in the cmd_catalog mirror (table_exists='f' via the sync). An
UNMARKED dangler means the sync is stale and the resolver can pin a ghost — re-run
scripts/sync_neuract_registry.py. Skips honestly when the tunnel/DB is unreachable."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.live


def test_no_unmarked_dangling_registry_rows():
    from data.registry.drift import check
    out = check()
    if "skipped" in out:
        pytest.skip(out["skipped"])
    assert out["dangling_unmarked"] == [], (
        f"stale registry mirror — {len(out['dangling_unmarked'])} dangling row(s) still stamped table_exists='t'; "
        f"re-run scripts/sync_neuract_registry.py: {out['dangling_unmarked']}")
