"""layer1b/resolve/has_data.py — 1b's has-data door: never resolve/offer an empty / never-wired / WIRED-BUT-SILENT
meter.

The row/value PROBES (value_counts / tables_with_values / tables_with_data / VALUE_MIN + their TTL caches) moved to
data/value_probe.py — they are data-layer concerns consumed by grounding.meaningful and data.lt_panels too, and living
here forced a grounding↔layer1b import cycle. Re-exported below so every existing importer keeps working.
[cycle-kill 2026-07-12]

What still LIVES here: the layer1b-facing meaningfulness delegation (has_meaningful_data) — the shared honest
has-data gate that routes through the grounding engine with a value-count fail-open. [neuract live-data filter]"""
from data.value_probe import (            # noqa: F401  (re-export; the probes' home is data/value_probe.py)
    VALUE_MIN, value_counts, tables_with_values, tables_with_data,
)


def has_meaningful_data(asset, page_key=None):
    """The SHARED honest has-data gate: present ∧ non_null ∧ MEANINGFUL for `page_key`.

    Delegates to the grounding engine (grounding.meaningful — the single source of truth), which routes the asset's
    schema fingerprint, checks the page's required metric class, and probes the latest row against the EDITABLE
    data_quality_policy knobs (padded-0 / denorm garbage / all-null-THD / reversed-CT energy). `asset` is the
    asset_candidates.as_asset() dict (or a bare neuract table name); `page_key` is the routed page (None ⇒ any-metric).

    True ⇒ the meter can render real values for the page; False ⇒ the caller honest-degrades with the machine cause from
    grounding.meaningful.probe(). Import is kept LAZY so pulling the 1b resolve package never drags the grounding
    engine (and its config/DB doors) into memory for probe-only callers. [DS-01/04/06, VC-09, has_data≠meaningful]
    """
    from grounding.meaningful import has_meaningful_data as _grounded
    try:
        return _grounded(asset, page_key)
    except Exception as e:  # fail-open to the row/value signal so a probe bug can't blanket-blank real assets
        import sys
        sys.stderr.write(f"[has_meaningful_data] probe failed ({str(e)[:80]}) — falling back to value-count\n")
        table = asset.get("table") if isinstance(asset, dict) else asset
        return bool(table) and table in tables_with_values([table])
