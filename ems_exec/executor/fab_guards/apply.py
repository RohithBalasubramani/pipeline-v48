"""fab_guards/apply.py — the ONE post-fill guard entry wired into fill.py (after every honest fill pass):
sequences CLASS 1 → CLASS 2/3 → CLASS 4 over the completed payload."""
from __future__ import annotations

import copy

from ems_exec.executor.fab_guards.knobs import _guard_on
from ems_exec.executor.fab_guards.class1_epoch import _apply_class1
from ems_exec.executor.fab_guards.class23_source import _apply_class2_class3
from ems_exec.executor.fab_guards.class4_seed import _apply_class4_seed_leak, _written_toks


def _mode():
    """fab_guards.mode ∈ 'enforce' (default — blanks live, byte-identical to legacy) | 'report' (SHADOW: compute every
    class verdict against a deep COPY, record the would-blank gaps marked shadow=True, but NEVER mutate the served
    payload). Shadow mode is the fleet-audit + cert-baseline instrument: it lets every guard rework be verified against
    real traffic (report the deltas) before any enforce-mode change ships. Fail-open to 'enforce'."""
    try:
        from config.app_config import cfg
        return str(cfg("fab_guards.mode", "enforce")).strip().lower()
    except Exception:
        return "enforce"

def _roster_exempt_on():
    """fab_guards.exempt_roster_slots [default off]: CLASS 2/3 must not second-guess the roster interpreter INSIDE its
    own recipe slots. The guards audit by the AI's declared FIELDS — but on a panel-aggregate card the AI's field often
    binds the panel's own control-table column (absent/dead), while the RECIPE writes the real member-rolled value to
    the SAME leaf; the field-keyed guard then blanks that real value as a 'no-source stray' (card 15: the roster wrote
    3270 kVA, CLASS 2/3 nulled it → the whole card rendered blank). Per-leaf honesty inside a recipe slot is the
    ROSTER's job — it writes its own honest nulls with per-leaf gap reasons (roster_gaps). Fail-open to OFF."""
    try:
        from config.app_config import flag_on
        return flag_on("fab_guards.exempt_roster_slots", False)
    except Exception:
        return False


def _roster_slot_paths(roster_slot_prefixes, out):
    """Expand the recipe slot strings ('card.view.value', 'card.view.metrics', 'flow.vm.kpis', 'a[]') into the concrete
    LEAF paths currently under them in `out` — the same dotted/indexed path vocabulary CLASS 2/3's skip set speaks
    (both with and without the 'data.' twin either address form resolves). '[]' suffixes are normalized away; a slot
    prefix covers its whole subtree."""
    prefixes = []
    for s in (roster_slot_prefixes or []):
        s = str(s or "").strip()
        if s.endswith("[]"):
            s = s[:-2]
        if s:
            prefixes.append(s)
            prefixes.append(s[5:] if s.startswith("data.") else "data." + s)

    paths = set()

    def walk(node, path):
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, f"{path}.{k}" if path else str(k))
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]")
        else:
            if any(path == p or path.startswith(p + ".") or path.startswith(p + "[") for p in prefixes):
                paths.add(path)
                paths.add("data." + path)

    if prefixes:
        walk(out, "")
    return paths


def _run_classes(out, fields, present_cols, asset_table, default_payload, written_paths, shape_ref,
                 roster_slot_prefixes, agg_row_present):
    """Run CLASS 1 → (roster-slot skip) → CLASS 2/3 → CLASS 4 against `out` (mutating it) and return the gap records.
    The SAME body serves both enforce mode (out = the served payload) and report mode (out = a throwaway deep copy)."""
    gaps = []
    try:
        skip = _apply_class1(out, gaps) if _guard_on("epoch_ms") else set()
    except Exception:
        skip = set()
    try:
        if roster_slot_prefixes and _roster_exempt_on():
            skip = set(skip) | _roster_slot_paths(roster_slot_prefixes, out)
    except Exception:
        pass
    try:
        _apply_class2_class3(out, fields or [], present_cols or frozenset(), asset_table, gaps, skip,
                             agg_row_present=agg_row_present)
    except Exception:
        pass
    try:
        if _guard_on("seed_leak") and default_payload is not None:
            _apply_class4_seed_leak(out, default_payload, _written_toks(written_paths), gaps, raw_default=shape_ref)
    except Exception:
        pass
    return gaps


def apply(out, fields, present_cols, asset_table, default_payload=None, written_paths=None, shape_ref=None,
          roster_slot_prefixes=None, card_id=None, agg_row_present=False):
    """Scan the FINISHED payload and blank the four fabrication CLASSES slot-independently. Returns (out, gaps): the
    payload and the per-leaf gap records the caller MERGES into its gaps channel. Never raises — a guard that throws
    leaves the payload as it found it (fail-open on the honest fill, never fabricates).

    `default_payload` (optional) = the card's STRIPPED default skeleton (card_payloads.payload_stripped); `shape_ref`
    (optional) = the card's RAW harvested default (card_payloads.payload); `written_paths` = the leaf paths fill() wrote
    real. Together they drive CLASS 4 (seed-leak): a DATA leaf (raw != stripped) that is UNWRITTEN and byte-identical to
    its RAW default is an unstripped seed → blanked; a METADATA leaf (raw == stripped) is exempt whatever its key. When
    `shape_ref` is absent CLASS 4 falls back to the legacy chrome-vocab wall (under-blank preference).

    `roster_slot_prefixes` (flag fab_guards.exempt_roster_slots) = the card's recipe slot paths; leaves under them are
    ROSTER-written and exempt from the field-keyed CLASS 2/3 audit. `agg_row_present` (flag
    fab_guards.null_column_writer_aware) = this is a panel-aggregate fill (values came from the member roll-up, not
    asset_table), so CLASS 2's column-logged audit against asset_table is invalid and is skipped. `card_id` stamps
    every gap so the reason channel is card-attributed (closes the telemetry attribution gap).

    MODE (fab_guards.mode): 'enforce' (default) mutates `out`; 'report' runs every class against a deep COPY and returns
    the would-blank gaps marked shadow=True with `out` UNCHANGED — the audit/cert instrument."""
    gaps = []
    if not isinstance(out, dict):
        return out, gaps
    report = _mode() == "report"
    target = copy.deepcopy(out) if report else out
    gaps = _run_classes(target, fields, present_cols, asset_table, default_payload, written_paths, shape_ref,
                        roster_slot_prefixes, agg_row_present)
    for g in gaps:
        if card_id is not None:
            g["card_id"] = card_id
        if report:
            g["shadow"] = True
    return out, gaps                       # report mode returns the ORIGINAL (unmutated) out + shadow gaps
