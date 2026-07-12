"""fab_guards/apply.py — the ONE post-fill guard entry wired into fill.py (after every honest fill pass):
sequences CLASS 1 → CLASS 2/3 → CLASS 4 over the completed payload."""
from __future__ import annotations

from ems_exec.executor.fab_guards.knobs import _guard_on
from ems_exec.executor.fab_guards.class1_epoch import _apply_class1
from ems_exec.executor.fab_guards.class23_source import _apply_class2_class3
from ems_exec.executor.fab_guards.class4_seed import _apply_class4_seed_leak, _written_toks

def apply(out, fields, present_cols, asset_table, default_payload=None, written_paths=None, shape_ref=None):
    """Scan the FINISHED payload and blank the four fabrication CLASSES slot-independently. Returns (out, gaps): the
    (mutated) payload and the per-leaf gap records the caller MERGES into its gaps channel. Never raises — a guard that
    throws leaves the payload as it found it (fail-open on the honest fill, never fabricates).

    `default_payload` (optional) = the card's STRIPPED default skeleton (card_payloads.payload_stripped); `shape_ref`
    (optional) = the card's RAW harvested default (card_payloads.payload); `written_paths` = the leaf paths fill() wrote
    real. Together they drive CLASS 4 (seed-leak): a DATA leaf (raw != stripped) that is UNWRITTEN and byte-identical to
    its RAW default is an unstripped seed → blanked; a METADATA leaf (raw == stripped) is exempt whatever its key. When
    `shape_ref` is absent CLASS 4 falls back to the legacy chrome-vocab wall (under-blank preference)."""
    gaps = []
    if not isinstance(out, dict):
        return out, gaps
    try:
        skip = _apply_class1(out, gaps) if _guard_on("epoch_ms") else set()
    except Exception:
        skip = set()
    try:
        _apply_class2_class3(out, fields or [], present_cols or frozenset(), asset_table, gaps, skip)
    except Exception:
        pass
    try:
        if _guard_on("seed_leak") and default_payload is not None:
            _apply_class4_seed_leak(out, default_payload, _written_toks(written_paths), gaps, raw_default=shape_ref)
    except Exception:
        pass
    return out, gaps
