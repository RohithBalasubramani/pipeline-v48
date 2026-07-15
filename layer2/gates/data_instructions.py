"""layer2/gates/data_instructions.py — gate_data_instructions: the fields[] structural gate (every field a real
basket column / const / $ctx)."""
import re as _re

from layer2.gates.basket import _bindable, _col_issue
from layer2.gates.honest_blank import enforce_honest_blank


def _slot_leaf_key(slot):
    m = _re.findall(r"[A-Za-z_][A-Za-z0-9_]*", str(slot or ""))
    return m[-1] if m else ""


def _time_axis_slot(key):
    """Is this leaf key a designated TIME AXIS (legal target for a kind='time' atom)? Authority = the CLASS-1
    exemption vocabulary (fab_guards.time_axis_suffixes/exact + vocab.time_axis_keys) — the SAME list the post-fill
    epoch guard honors — plus the slot-catalog structural net ('timestamp'/…StartMs/…EndMs) and the '…points'
    cursor family the prompt licenses. Emit mis-declared kind=time onto value/Y-scale leaves and the series-time
    fill wrote epoch-ms bucket axes there (the whole epoch_ms_leak class) [audit 2026-07-14, 13 F1]."""
    k = (key or "").lower()
    if k.endswith("points"):
        return True
    try:
        from ems_exec.executor.fab_guards.knobs import _is_time_axis_key as _fg
        if _fg(k):
            return True
    except Exception:
        pass
    from layer2.emit.slot_catalog import _is_time_axis_key as _sc
    return _sc(k)

def gate_data_instructions(data_instructions, basket, *, is_group_card=False, fields_optional=False,
                           answerability=None, exact_metadata=None):
    # HONEST-BLANK PRE-PASS (SEAM 2): drop proxy / reused-binding / no-column fields IN PLACE before validation, so a
    # slot the asset can't measure ships an honest blank, not a fabricated number. Telemetry rides di._honest_blanked
    # (NOT a card gate — per-leaf degradation); the reduced fields[] is then validated below as usual.
    # `exact_metadata` (optional) = the card's authored skeleton — the sibling-unit slot-quantity evidence [card 61].
    _hb = enforce_honest_blank(data_instructions, basket, is_group_card=is_group_card, exact_metadata=exact_metadata)
    if _hb:
        existing = data_instructions.get("_honest_blanked") or []
        data_instructions["_honest_blanked"] = existing + _hb
    real, failed = _bindable(basket)
    issues = []
    _time_drops = []                                   # mis-targeted kind=time fields to remove (never epoch-fill)
    fields = data_instructions.get("fields") or []
    if not fields:
        # A pure-chrome / special-renderer card (handling_class in app_config gates.fields_optional_classes: nav_index
        # chrome, narrative_ai/topology_sld/asset_3d whose DATA is built by run_special, not fields[]) legitimately
        # carries fields: [] — its render is its exact_metadata / a widget envelope, nothing to bind. Any fields it
        # DOES emit are still fully policed below.
        # A member-scope ROSTER emission is a data binding too: fields:[] beside a non-empty data_instructions.roster
        # CONFORMS — the card's DATA rides the roster interpreter, not fields[], and gate_roster normalizes that
        # roster to the recipe truth right after this gate. Flagging it shipped a STALE payload_error on cards whose
        # normalized render was fine (the page-01 card-5 class: 'fields is empty' + already-backfilled roster issues).
        # ★ HONEST-NONE CARVE-OUT [card 74, empty-fields family]: an emission that DECLARES answerability="none" (or
        # arrives with an EMPTY column basket — the asset logs no metric columns, so there is literally nothing to
        # bind) is the AI's CORRECT honest escape, not a defect. Stamping it a card-blocking payload_error was a
        # verdict acting as a render gate (mandate breach: per-LEAF degradation, verdicts are telemetry). The card
        # renders its metadata frame with honest-blank leaves; the "none" still drives the reflect re-route.
        # ★ GATE-EMPTIED CARVE-OUT [card 52, quantity-wall family]: when enforce_honest_blank itself removed every
        # field (_honest_blanked non-empty — proxies/consts the wall correctly killed), the emptiness is the GATE's
        # honest verdict, not an emit defect. The card renders its skeleton with per-leaf reasons; erroring here would
        # punish the AI for the gate doing its job (verdicts are telemetry, never a render gate).
        if not fields_optional and not data_instructions.get("roster") \
                and not data_instructions.get("_honest_blanked") \
                and not (str(answerability or "").lower() == "none" or not real):
            issues.append("data_instructions.fields is empty")
    for i, f in enumerate(fields):
        kind, src, col = f.get("kind"), f.get("source"), f.get("column")
        # LITERAL / CHROME fields — a const value or a text label. The literal lives in exact_metadata, NOT a data
        # column; demanding a column here wrongly rejected every "Live Health" status text (source=='const' too).
        # source=='frame' = a fan-out / list-structure field the FRONTEND fills from the live frame (column_override
        # dropped its hallucinated column) — no column to bind here either.
        if kind in ("const", "text") or src in ("const", "frame"):
            if kind == "const" and f.get("value") is None:
                issues.append(f"fields[{i}] kind=const without a value")
            continue
        # TIME-AXIS field — the emit contract is {slot, kind:"time", role, source} with NO column and NO metric: the
        # executor fills the leaf from the card's OWN bucket-timestamp axis (fill._is_time_field →
        # _anchor_timestamps; the panel renderer rides the same axis), never from a measured column. Demanding a
        # resolved column here rejected every CONFORMING time emission ('fields[i] kind=time missing a resolved
        # column' — the cards 56/59 class). A timestamp-ish column it may still carry ('ts') is the executor's
        # compat net, not a basket column — nothing to police.
        if kind == "time":
            # TIME-ATOM TARGET GATE [audit 13 F1, epoch_ms_leak front door]: a kind=time atom may bind ONLY a
            # designated time-axis leaf — on a value/scale/marker slot the executor's series-time fill would write
            # an epoch-ms bucket axis there (CLASS-1 then blanks it, but the front door should refuse). fields[-
            # prefixed issue → the per-leaf partition (conforms stays True); the field is DROPPED so the executor
            # can never epoch-fill the leaf; the completion scan gives it its per-leaf reason.
            if not _time_axis_slot(_slot_leaf_key(f.get("slot"))):
                issues.append(f"fields[{i}] kind=time on a non-time-axis slot {f.get('slot')!r} — a value/scale/"
                              f"marker leaf is never a time axis; field dropped, leaf honest-blanks")
                _time_drops.append(i)
            continue
        if src == "$ctx":
            if not is_group_card:
                issues.append(f"fields[{i}] source=$ctx on a non-group card")
            continue
        # DERIVED — computed by a fn (the derivation LIBRARY) over base_columns; it has NO single resolved column.
        # Validate it carries the fn + its base inputs instead of demanding a column.
        if kind == "derived":
            if not f.get("fn"):
                issues.append(f"fields[{i}] kind=derived without fn")
            if not f.get("base_columns"):
                issues.append(f"fields[{i}] kind=derived without base_columns")
            continue
        # DIRECT live/test-db column fields.
        if src not in ("live", "test-db"):
            issues.append(f"fields[{i}] bad source {src!r} (want live|test-db|const|$ctx)")
        if col and col not in real:
            # A validate-FAIL column (present in `failed` — a REAL column with sparse/dead data on THIS meter) must NOT
            # block the card: the executor still fills its live rows and blanks the null rest PER-LEAF, so a
            # card-blocking payload_error here breaks the per-leaf-degradation mandate (verdicts are telemetry, never a
            # render gate — its own _col_issue text already says "leaf honest-blanks"). Record it as honest-blank
            # telemetry and KEEP the field so any live rows still fill. Only a genuinely HALLUCINATED column (absent from
            # the schema — not even a failed basket entry) is a hard defect, and those were already dropped by the
            # enforce_honest_blank pre-pass above, so this branch is the validate-fail case. [card 47: harmonics bound to
            # a thd_* column this UPS logs 100% null → honest-blank, not payload_error]
            if col in failed:
                data_instructions["_honest_blanked"] = (data_instructions.get("_honest_blanked") or []) + [_col_issue(i, col, failed)]
            else:
                issues.append(_col_issue(i, col, failed))
        if not col:
            issues.append(f"fields[{i}] kind={kind} missing a resolved column")
        if kind == "event" and not f.get("edge"):
            issues.append(f"fields[{i}] kind=event without edge")
    for i in reversed(_time_drops):                    # drop AFTER the loop (stable indices in the issue texts)
        del fields[i]
    return (not issues), issues
