"""config/nameplates.py — thin reader over cmd_catalog.asset_nameplate (seeded by manage.py seed_nameplates).

THE nameplate source for V48 (rated/contract/nominal/role/section/category per neuract asset table). NO hardcoded
rating anywhere — every number is an editable row. A missing/unknown rating returns None so the caller honest-degrades
the loading% slot (never fabricates a denominator). [RN-01/02/05/07, DS-10, DID-03, VC-05]

Also derives the full rating field-set from a single nameplate kVA (derive_ratings — ported from
CMD/backend2/core/config.py:16-47 feeder_rating_overrides, incl. the CRITICAL L-L→L-N nominal conversion so the
statutory band is drawn over the per-phase ~240 V data, not the stored 415 V L-L → a permanent fake violation), and the
per-asset→class-default→None contracted-kVA fallback (config.asset_class_defaults). All knobs are editable rows (config.rating_knobs). Honest-degrade
throughout — a missing input returns None, never a guessed value.
"""
import math
import re

from data.db_client import q
from config import rating_knobs as _rk
from config import asset_class_defaults as _acd

try:
    from config.failopen import cfg_safe as _cfg   # THE guarded cfg reader (D3)
except Exception:  # pragma: no cover — import-safe without the pipeline config on the path
    def _cfg(key, default):
        return default

_COLS = ["asset_table", "mfm_name", "rated_kva", "contracted_kva",
         "nominal_voltage_ll", "role", "section", "asset_category", "source"]

# ── real-per-asset rating gate (the class-default fabrication fix) ────────────────────────────────────────────────────
# A stored rated_kva is a REAL per-asset nameplate ONLY when it has genuine per-asset provenance. Otherwise it is a
# CLASS/SHEET fill — the premier-energies DB-mapping sheet backfilled a typical-for-the-category kVA onto assets the
# neuract plant has NO real rating for (neuract lt_mfm.rated_capacity_kva is NULL for ALL 320 assets; the CMD equipment
# sheet lists bpdb-* / most LT panels as having NO OCR source, yet every BPDB feeder landed a uniform 300.0). Treating
# such a class guess as a real denominator FABRICATES a load% / overload (card 8: 'BPDB-02 … 127.3% of its 300.0 kVA').
# So rated_kva is HONORED only when:
#   (1) its `source` is a trusted per-asset provenance (name_parse, or a future manual/OCR/datasheet seed) — DB-tunable
#       set config.app_config `nameplate.trusted_rating_sources`; OR
#   (2) the asset's OWN name embeds a kVA token EQUAL to the stored rating (e.g. 'UPS-01 CL:600KVA', '160 KVA UPS-01') —
#       the rating is written on the asset, so it is genuinely per-asset regardless of which sheet loaded the row.
# Anything else (a category/sheet fill with no per-asset corroboration) → rated_kva is nulled → the caller honest-degrades
# the loading% slot (None), NEVER a fabricated denominator. [RN-01/02/05, DS-10, DID-03; the card-8 class-default defect]
_TRUSTED_RATING_SOURCES = ("name_parse", "manual", "ocr", "datasheet", "nameplate", "asset_nameplate")

# a kVA value embedded in the asset name: '600kVA', '160 KVA', 'CL:600KVA' — a bare number immediately followed by 'kva'
# (word boundary). Excludes 'KVAR'/'KVARh' (reactive) and a trailing model number like 'Elite300' (no 'kva' suffix).
_NAME_KVA = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s*k\s*va(?![rh\w])", re.I)


def _trusted_sources():
    """The set of per-asset rating provenances that are honored WITHOUT name corroboration (DB-tunable, code default)."""
    try:
        v = _cfg("nameplate.trusted_rating_sources", list(_TRUSTED_RATING_SOURCES))
        if isinstance(v, (list, tuple, set)):
            return {str(s).strip().lower() for s in v}
    except Exception:
        pass
    return {s.lower() for s in _TRUSTED_RATING_SOURCES}


def _name_corroborates(mfm_name, rated):
    """True when the asset's own name embeds a kVA token EQUAL to `rated` (the rating is written on the asset → real
    per-asset). A ~1% tolerance absorbs 600 vs 600.0 rounding. False when the name has no kVA or a DIFFERENT one (a
    sheet value that contradicts the name is not trustworthy)."""
    try:
        r = float(rated)
    except (TypeError, ValueError):
        return False
    if r <= 0:
        return False
    for m in _NAME_KVA.finditer(mfm_name or ""):
        try:
            nk = float(m.group(1))
        except (TypeError, ValueError):
            continue
        if abs(nk - r) <= max(0.01, r * 0.01):
            return True
    return False


def _is_real_per_asset_rating(row):
    """Whether `row`'s stored rated_kva is a REAL per-asset nameplate (trusted source OR name-corroborated) vs a
    class/sheet-default fill (→ null it, honest-degrade the loading% denominator). A row with no rating is trivially
    'real' (None stays None)."""
    rated = row.get("rated_kva")
    if rated in (None, "", "NULL"):
        return True
    if str(row.get("source") or "").strip().lower() in _trusted_sources():
        return True
    return _name_corroborates(row.get("mfm_name"), rated)

# The feeder-PQ (equipment-detail power-quality) per-asset limit fields the CMD_V2 mapper reads before falling back to
# the IEEE-519 code default (powerQualityMapper.ts:169-175). A per-asset nameplate can carry these; absent one, the
# class default (config.asset_class_defaults) supplies the honest per-class value. NONE of these fabricate a rating.
_PQ_LIMIT_FIELDS = (
    "ieee_519_voltage_thd_limit_pct",
    "ieee_519_current_thd_limit_pct",
    "ieee_519_individual_harmonic_limit_pct",
    "flicker_pst_limit",
    "crest_factor_ideal",
)


def _num(x):
    return None if x in (None, "", "NULL") else float(x)


def get_nameplate(asset_table):
    """The full nameplate row for a neuract table_name → dict (rated_kva/contracted_kva/nominal_voltage_ll numeric,
    others text) or None if the asset has no nameplate row at all.

    The stored rated_kva (and its derived contracted_kva) is NULLED here when it is a CLASS/SHEET-default fill rather
    than a real per-asset nameplate (see _is_real_per_asset_rating) — so EVERY consumer (the rated_kva/contracted_kva
    accessors, derive_ratings_for, and the executor's raw-row nameplate:rated_kva fill in gaps/derived) honest-degrades
    the loading% denominator to None instead of fabricating a load% / overload off a class guess. The identity /
    policy fields (role, section, asset_category, nominal_voltage_ll) are always preserved."""
    rows = q("cmd_catalog",
             "SELECT " + ",".join(_COLS) + " FROM asset_nameplate "
             f"WHERE asset_table='{_esc(asset_table)}'")
    if not rows:
        return None
    r = rows[0]
    d = dict(zip(_COLS, r))
    for k in ("rated_kva", "contracted_kva", "nominal_voltage_ll"):
        d[k] = _num(d[k])
    if not _is_real_per_asset_rating(d):
        # a class/sheet-default rating is NOT a real nameplate — drop the denominator (and its derived contract) so no
        # caller fabricates a load% from it. Keep the raw sheet value under `rated_kva_class_default` for diagnostics.
        d["rated_kva_class_default"] = d["rated_kva"]
        d["rated_kva"] = None
        d["contracted_kva"] = None
    return d


def rated_kva(asset_table):
    """Just the nameplate rated kVA (the loading% denominator), or None → honest-degrade."""
    np = get_nameplate(asset_table)
    return np["rated_kva"] if np else None


def nominal_voltage_ll(asset_table):
    np = get_nameplate(asset_table)
    return np["nominal_voltage_ll"] if np else None


def contracted_kva(asset_table):
    """The contracted / sanctioned kVA for the asset. Per-asset nameplate row (asset_nameplate.contracted_kva) →
    class contracted-fraction of the honest per-asset rated_kva (config.asset_class_defaults) → None. V48 seeds
    contracted_kva NULL today, so this fills it from the class default WITHOUT fabricating a rating: it needs the
    honest per-asset rated_kva; with no rating it honest-degrades to None."""
    np = get_nameplate(asset_table)
    if not np:
        return None
    if np.get("contracted_kva") is not None:
        return np["contracted_kva"]
    # derive from the class contracted fraction over the honest per-asset rated_kva (never a class-guessed rating):
    # contracted_kva ≈ rated_kva × contracted_frac. The class fraction (config_defaults' contracted/rated ratio) is
    # carried on the class default; absent one, fall back to the global rating.contracted_factor knob.
    rated = np.get("rated_kva")
    cat = np.get("asset_category")
    if rated is None or not cat:
        return None
    frac = _acd.class_field(cat, "contracted_frac", _rk.contracted_factor())
    return round(float(rated) * float(frac), 1)


def derive_ratings(rated_kva, nominal_ll=None):
    """The full rating field-set derived from a single nameplate kVA (ports backend2 feeder_rating_overrides).

    Returns a dict of rated_kva / rated_kw / rated_current_a / current_high_threshold_a / contracted_kw /
    critical_load_kw / energy_target_kwh_today / voltage_nominal_v (the per-phase L-N nominal). Honest-degrade: a
    missing / non-positive rated_kva → {} (caller renders '—', never a fabricated denominator).

    CRITICAL L-N conversion: nominal_ll is a line-to-LINE value (415 V default, or 11 kV for HT). The per-phase columns
    the data carries are line-to-NEUTRAL (~240 V), so the statutory band MUST be drawn over nom_ln = nom_ll / sqrt(3)
    or it reads as a permanent fake violation (works at any level: 415→240, 11k→6.35k).

    All factors are editable rows (config.rating_knobs): PF, LV line V, 120% alarm, 0.9× contracted, 0.5× critical,
    12h energy target."""
    if not rated_kva or float(rated_kva) <= 0:
        return {}
    kva = float(rated_kva)
    pf = _rk.feeder_pf()
    line_v = float(nominal_ll) if nominal_ll not in (None, "", "NULL") else _rk.lv_line_v()
    kw = round(kva * pf)
    rated_a = round(kva * 1000.0 / (math.sqrt(3) * line_v)) if line_v > 0 else None
    nom_ln = round(line_v / math.sqrt(3)) if line_v > 0 else None
    out = {
        "rated_kva": round(kva, 1),
        "rated_kw": kw,
        "rated_current_a": rated_a,
        "current_high_threshold_a": (round(rated_a * _rk.current_alarm_factor()) if rated_a is not None else None),
        "contracted_kw": round(kw * _rk.contracted_factor()),
        "critical_load_kw": round(kw * _rk.critical_load_factor()),
        "energy_target_kwh_today": round(kw * _rk.energy_target_hours()),
        "voltage_nominal_v": nom_ln,   # per-phase L-N — matches the measured basis (the fake-violation fix)
        "nominal_voltage_v": nom_ln,   # both key spellings the mappers read
    }
    return out


def derive_ratings_for(asset_table):
    """derive_ratings for an asset by neuract table_name — pulls the honest per-asset rated_kva + nominal_voltage_ll
    from asset_nameplate first. {} when the asset has no rating (honest-degrade)."""
    np = get_nameplate(asset_table)
    if not np:
        return {}
    return derive_ratings(np.get("rated_kva"), np.get("nominal_voltage_ll"))


def pq_limit(asset_table, field, default=None):
    """One feeder-PQ limit field for an asset, resolved per-asset nameplate row → class default → `default` (None).
    `field` ∈ _PQ_LIMIT_FIELDS (ieee_519_*_thd_limit_pct / ieee_519_individual_harmonic_limit_pct / flicker_pst_limit /
    crest_factor_ideal). Honest-degrade: no per-asset value AND no class default → `default`, so the caller keeps the
    CMD_V2 IEEE-519 code fallback rather than a fabricated per-asset limit. Ports powerQualityMapper.ts:169-175.

    DB-down safe: a nameplate-read failure degrades to the class default (which is itself fail-open), so the PQ path
    still gets the honest per-class limit with the catalog DB unreachable — never raises, never blocks the mapper."""
    try:
        np = get_nameplate(asset_table)
    except Exception:
        np = None   # catalog DB unreachable → fall through to the class default (fail-open, honest-degrade)
    if np:
        v = np.get(field)
        if v not in (None, "", "NULL"):
            try:
                return float(v)
            except (TypeError, ValueError):
                return v
        cat = np.get("asset_category")
        if cat:
            cv = _acd.class_field(cat, field, None)
            if cv is not None:
                return cv
    return default


def role_section(asset_table):
    """(role, section) for heatmap sectioning / limit lookup, or (None, None)."""
    np = get_nameplate(asset_table)
    return (np["role"], np["section"]) if np else (None, None)


def asset_category(asset_table):
    np = get_nameplate(asset_table)
    return np["asset_category"] if np else None


from config.policy_read import esc as _esc  # the ONE shared SQL-quote escape  # noqa: E402
