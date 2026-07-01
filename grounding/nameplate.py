"""grounding/nameplate.py — the PRE grounding engine for an asset's NAMEPLATE fact-sheet fragment.

THE single deterministic (no-AI) unit that answers "what is this asset's rated kVA / contracted kVA / nominal LL
voltage / role / section / category — and is that a REAL number or unknown?". It is a thin, side-effect-free wrapper
over `config.nameplates` (the editable `cmd_catalog.asset_nameplate` table). It NEVER fabricates a rating: a missing
nameplate row, or a present row with a NULL rated_kva, yields `rated_kva=None` + a machine-readable `no_nameplate`
reason so the caller honest-degrades the ONE affected slot (loading% / headroom / %-used) instead of the whole card.

Covers: RN-01 (no rated denominator → real value where a nameplate exists, honest-blank where not),
RN-02 (name-form ratings already parsed at seed time — read here uniformly), RN-05 (role/section/asset_category for
heatmap sectioning + limit lookup, sourced from the table not name-guess heuristics), RN-07 (static identity plate for
a wired-but-silent asset), DS-10 (rated/contract/nominal absent from the live DB → this table is the ONLY source),
DID-03 (never advertise a real_exact rating for a value the DB can't produce — presence is gated on the table row),
VC-05 (kills the hardcoded fake NAMEPLATE dict — every number is an editable row).

ALL policy (the numbers, the role/section strings, the reason sentence) lives in DB config accessors — this file holds
ZERO hardcoded ratings/mappings/reason strings.
"""
from config import nameplates as _np
from config import reason_templates as _reasons


# ── the primary grounding call ──────────────────────────────────────────────────────────────────────────────────────
def resolve(asset):
    """The nameplate FACT-SHEET fragment for an asset → a dict the grounding kit folds into the card's fact-sheet:

        { asset_table, mfm_name,
          rated_kva, contracted_kva, nominal_voltage_ll,   # numeric or None (NEVER fabricated)
          role, section, asset_category, source,           # text or None
          has_nameplate: bool,                             # a row exists at all (RN-07 identity plate)
          has_rated:     bool,                             # a real rated_kva denominator is available
          reason:        str|None }                        # machine-readable honest-blank reason when has_rated is False

    `asset` may be a neuract table_name (str) or a dict/object carrying one (asset_table / table_name / table). When no
    table can be identified, or no nameplate row exists, `rated_kva`/`has_rated` degrade honestly with a reason — the
    caller blanks only the loading% slot, never invents a denominator.
    """
    table = _asset_table(asset)
    name = _asset_name(asset)

    if not table:
        # no identifiable table → cannot look up a nameplate; honest-blank the whole fragment (no fabrication).
        return _blank_fragment(table, name, cause="no_nameplate")

    row = _np.get_nameplate(table)
    if row is None:
        # no editable nameplate row for this asset → honest-blank (RN-01/RN-07: caller may still show a bare frame).
        return _blank_fragment(table, name, cause="no_nameplate")

    rated = row.get("rated_kva")
    has_rated = rated is not None
    frag = {
        "asset_table": row.get("asset_table") or table,
        "mfm_name": row.get("mfm_name") or name,
        "rated_kva": rated,
        "contracted_kva": row.get("contracted_kva"),
        "nominal_voltage_ll": row.get("nominal_voltage_ll"),
        "role": row.get("role"),
        "section": row.get("section"),
        "asset_category": row.get("asset_category"),
        "source": row.get("source"),
        "has_nameplate": True,
        "has_rated": has_rated,
        # a row without a rated_kva still gives identity/role/section — only the loading% denominator is missing.
        "reason": None if has_rated else _reasons.reason("no_nameplate", asset=(row.get("mfm_name") or name or table)),
    }
    return frag


# ── convenience single-value reads (thin pass-throughs to config.nameplates, kept honest) ───────────────────────────
def rated_kva(asset):
    """The rated-kVA loading% denominator for an asset, or None → the caller honest-degrades the loading% slot."""
    table = _asset_table(asset)
    return _np.rated_kva(table) if table else None


def nominal_voltage_ll(asset):
    """Nominal line-to-line voltage (reference lines / statutory band), or None."""
    table = _asset_table(asset)
    return _np.nominal_voltage_ll(table) if table else None


def role_section(asset):
    """(role, section) for heatmap sectioning / per-category limit lookup, or (None, None). [RN-05]"""
    table = _asset_table(asset)
    return _np.role_section(table) if table else (None, None)


def asset_category(asset):
    """The asset_category (drives per-category warn/trip limits), or None. [RN-05]"""
    table = _asset_table(asset)
    return _np.asset_category(table) if table else None


def has_rated(asset):
    """True iff a REAL rated_kva denominator exists for this asset (a loading% slot can render a real number)."""
    return rated_kva(asset) is not None


# ── internals ───────────────────────────────────────────────────────────────────────────────────────────────────────
def _blank_fragment(table, name, cause):
    """A fully-shaped fragment with no rated value — every numeric field None, has_* False, honest reason set. Keeps the
    fact-sheet shape uniform so downstream code branches on has_rated/has_nameplate, never on a missing key."""
    return {
        "asset_table": table,
        "mfm_name": name,
        "rated_kva": None,
        "contracted_kva": None,
        "nominal_voltage_ll": None,
        "role": None,
        "section": None,
        "asset_category": None,
        "source": None,
        "has_nameplate": False,
        "has_rated": False,
        "reason": _reasons.reason(cause, asset=(name or table or "asset")),
    }


def _asset_table(asset):
    """Extract a neuract table_name from a str or a dict/object (asset_table / table_name / table)."""
    if asset is None:
        return None
    if isinstance(asset, str):
        return asset.strip() or None
    if isinstance(asset, dict):
        for k in ("asset_table", "table_name", "table"):
            v = asset.get(k)
            if v:
                return str(v).strip() or None
        return None
    for k in ("asset_table", "table_name", "table"):
        v = getattr(asset, k, None)
        if v:
            return str(v).strip() or None
    return None


def _asset_name(asset):
    """A human name for the reason sentence, if the caller carried one alongside the table."""
    if isinstance(asset, dict):
        for k in ("mfm_name", "name", "asset_name"):
            v = asset.get(k)
            if v:
                return str(v).strip()
        return None
    if not isinstance(asset, str):
        for k in ("mfm_name", "name", "asset_name"):
            v = getattr(asset, k, None)
            if v:
                return str(v).strip()
    return None
