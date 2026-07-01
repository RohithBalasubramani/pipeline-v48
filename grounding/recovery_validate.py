"""grounding/recovery_validate.py — the PRE grounding engine that decides, for a DEAD/ABSENT slot, whether a real
derivation can still fill it from columns that ARE present and populated on the asset — WITHOUT ever fabricating.

The one deterministic (no-AI) question this unit answers: "the card wants metric X but the direct column is missing or
uniformly NULL — is there a registered recovery fn whose base columns are ALL present AND actually fetched (non-null) on
this asset (nameplate pseudo-columns satisfied by a REAL nameplate row)?" If yes → the slot is recoverable (bind the
fn, tagged with its config fidelity); if no → honest-blank with a machine-readable reason. Every fn↔base_columns↔
fidelity fact is an EDITABLE ROW in `cmd_catalog.derivation_binding` (read via config.derivation_binding) — this file
holds ZERO hardcoded fn/base maps.

The gate is exactly the contract's "recovery_validate: for a dead slot, is there a registry.LIBRARY fn whose
base_columns ⊆ present ∧ fetched?" plus the nameplate-pseudo-column check, producing `build_derivation_catalog_for_asset`.

Covers: DID-02 (validate fn/base_columns before binding — drop a recovery whose inputs the asset can't feed),
DID-03/DID-05 (nameplate/PQ metrics whose base columns don't exist → NOT offered as recoverable; degrade with a real
reason instead of advertising a fidelity the data can't back), DS-04 (thd_compliance_ieee519 IS recoverable from the
populated current-THD columns → offered; voltage-THD/harmonic have no recoverable inputs → honest-blank),
VC-05 (a nameplate-derived loading% is only recoverable when a REAL rated_kva row exists).
"""
from config import derivation_binding as _bind
from config import reason_templates as _reasons
from config import nameplates as _np
from layer1b.basket.col_dict import real_table_cols, latest_nonnull

_NAMEPLATE_PREFIX = "nameplate:"


# ── the core slot check ─────────────────────────────────────────────────────────────────────────────────────────────
def is_recoverable(metric, present, fetched, asset_table=None):
    """Deterministic verdict for ONE metric on a slot whose direct column is dead/absent.

    A metric is recoverable iff a `derivation_binding` row exists AND every base column it needs is satisfiable:
      · a real (non-nameplate) base column must be BOTH present in the schema AND actually populated (in `fetched`) —
        a column that exists but is uniformly NULL cannot feed the fn, so it is NOT satisfiable (DID-02/DID-05);
      · a `nameplate:<field>` pseudo-column is satisfied only when the asset's nameplate row supplies that field with a
        real value (e.g. nameplate:rated_kva needs asset_nameplate.rated_kva not None) — never fabricated (VC-05/DID-03).

    Returns a verdict dict:
      { recoverable: bool, metric, fn, fidelity, base_columns,
        missing: [base cols that blocked it],  reason: str|None (set only when NOT recoverable) }
    """
    present = set(present or [])
    fetched = set(fetched or [])
    b = _bind.binding(metric)
    if not b:
        return _verdict(metric, False, None, None, [], missing=[],
                        reason=_reasons.reason("structurally_null", metric=metric))

    missing = []
    for col in b["base_columns"]:
        if col.startswith(_NAMEPLATE_PREFIX):
            if not _nameplate_field_available(col, asset_table):
                missing.append(col)
            continue
        # a real base column must be present in the schema AND non-null in the latest fetched row
        if col not in present or col not in fetched:
            missing.append(col)

    if missing:
        return _verdict(metric, False, b["fn"], b["fidelity"], b["base_columns"], missing=missing,
                        reason=_reasons.reason("structurally_null", metric=metric))
    return _verdict(metric, True, b["fn"], b["fidelity"], b["base_columns"], missing=[], reason=None)


def recover_for_slot(slot_metric, present, fetched, asset_table=None):
    """Convenience wrapper: for a single dead slot's metric, the recovery verdict (or a not-recoverable verdict when the
    slot names no registered metric). Same shape as is_recoverable so the caller branches uniformly."""
    return is_recoverable(slot_metric, present, fetched, asset_table=asset_table)


# ── the asset-level catalog builder ─────────────────────────────────────────────────────────────────────────────────
def build_derivation_catalog_for_asset(asset_table, present=None, fetched=None, wanted_metrics=None):
    """The per-asset RECOVERY CATALOG — every registered derivation, split into what THIS asset can actually recover vs
    what it honest-blanks, given its real present/fetched columns. This is the fact-sheet fragment the grounding kit
    hands L3 so the AI only ever substitutes among PRE-VERIFIED grounded alternatives (never a fn the asset can't feed).

    `present`  — the asset's physical columns (defaults to a live information_schema probe of `asset_table`).
    `fetched`  — the non-null columns in the asset's latest row (defaults to a live latest-row probe). A column present
                 but uniformly NULL is treated as NOT fetched, so a recovery bound to it correctly honest-blanks.
    `wanted_metrics` — optional restriction to the metrics the card actually needs (else every registered binding).

    Returns:
      { asset_table, present, fetched,
        recoverable: { metric: {fn, fidelity, base_columns} },   # bind these; each input verified present+populated
        blocked:     { metric: {fn, fidelity, base_columns, missing, reason} } }   # honest-blank these with the reason
    """
    if present is None:
        present = _probe_present(asset_table)
    if fetched is None:
        fetched = _probe_fetched(asset_table)
    present = set(present or [])
    fetched = set(fetched or [])

    metrics = list(wanted_metrics) if wanted_metrics else [b["metric"] for b in _bind.all_bindings()]

    recoverable, blocked = {}, {}
    for metric in metrics:
        v = is_recoverable(metric, present, fetched, asset_table=asset_table)
        if v["recoverable"]:
            recoverable[metric] = {"fn": v["fn"], "fidelity": v["fidelity"], "base_columns": v["base_columns"]}
        else:
            blocked[metric] = {"fn": v["fn"], "fidelity": v["fidelity"], "base_columns": v["base_columns"],
                               "missing": v["missing"], "reason": v["reason"]}

    return {
        "asset_table": asset_table,
        "present": sorted(present),
        "fetched": sorted(fetched),
        "recoverable": recoverable,
        "blocked": blocked,
    }


# ── internals ───────────────────────────────────────────────────────────────────────────────────────────────────────
def _nameplate_field_available(pseudo_col, asset_table):
    """Is a `nameplate:<field>` pseudo-base-column satisfiable — i.e. does the asset's nameplate row carry that field
    with a REAL (non-None) value? Reads config.nameplates (the editable asset_nameplate table); never fabricates."""
    if not asset_table:
        return False
    field = pseudo_col[len(_NAMEPLATE_PREFIX):]
    row = _np.get_nameplate(asset_table)
    if row is None:
        return False
    return row.get(field) is not None


def _probe_present(asset_table):
    """The asset's physical columns from the live schema (reuses layer1b's information_schema probe). [] on no table."""
    if not asset_table:
        return set()
    try:
        return real_table_cols(asset_table)
    except Exception:
        return set()


def _probe_fetched(asset_table):
    """The columns actually POPULATED (non-null) in the asset's latest row — a present-but-uniformly-NULL column is NOT
    fetched, so a recovery whose input is dead correctly honest-blanks. Reuses layer1b's latest-non-null probe."""
    if not asset_table:
        return set()
    try:
        return latest_nonnull(asset_table)
    except Exception:
        return set()


def _verdict(metric, recoverable, fn, fidelity, base_columns, missing, reason):
    return {"metric": metric, "recoverable": recoverable, "fn": fn, "fidelity": fidelity,
            "base_columns": base_columns, "missing": missing, "reason": reason}
