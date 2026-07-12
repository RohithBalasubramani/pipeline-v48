"""layer2/emit/equipment_facts.py — VERBATIM equipment-registry facts for the Layer-2 user message. [stream C]

Single concern: render the LOCAL equipment schema's per-asset ground truth (cmd_catalog.equipment — human alias,
bay role, section/zone, load_profile, node feed edges, breaker rating, RTM status bands, energy-register direction)
as additive FACT LINES beside the existing NAMEPLATE/DATA WINDOW facts, so the emit AI grounds loading/threshold/
labelling claims in real registry rows instead of guessing. FACTS ONLY — no vocabulary, no ranking, no scaling:
the never-rescale clause ships INSIDE the energy line because a scale factor applied to a reading is fabrication.

Every accessor is fail-open ('' / () on miss, dup-table twin, knob-off, or outage — never raises), so an asset with
no equipment rows produces BYTE-IDENTICAL prompts to the pre-wiring pipeline (cert safety). All reads ride the
data/equipment single door (:5432-local; the flaky :5433 tunnel is never touched). Knob: app_config
`equipment.facts.enabled` (code default 'on'; seed db/seed_equipment_ai_context.sql).
"""
from __future__ import annotations

def _enabled():
    """The equipment-facts knob (equipment.facts.enabled, default 'on'). DB-down → the CODE default (on) — the
    accessors below are themselves fail-open, so a dead equipment schema still degrades to '' per line."""
    try:
        from config.app_config import flag_on
        return flag_on("equipment.facts.enabled", True)   # THE boolean-knob vocabulary (D6); default-on preserved
    except Exception:
        return True


def _table(asset):
    return (asset or {}).get("table") if isinstance(asset, dict) else None


def equipment_line(asset):
    """'EQUIPMENT (…): aka=… | bay_role=… | section=… | zone=… | load_profile=… | fed_by=… | feeds=…' or ''.
    Only populated fields are shown; the whole line is omitted when the bridge resolves nothing (miss/dup/outage)."""
    tbl = _table(asset)
    if not (tbl and _enabled()):
        return ""
    try:
        from data.equipment import bridge as _b
        row = _b.eq_row_for_table(tbl)
        if not row:
            return ""
        bits = []
        aka = (row.get("name") or "").strip()
        if aka and aka != (asset or {}).get("name"):
            bits.append(f"aka={aka}")
        for key, label in (("role", "bay_role"), ("section", "section"), ("zone", "zone"),
                           ("load_profile", "load_profile"), ("asset_category", "category")):
            v = (row.get(key) or "").strip() if isinstance(row.get(key), str) else row.get(key)
            if v:
                bits.append(f"{label}={v}")
        fed_by, feeds = _b.feeds_fed_by(tbl)
        if fed_by:
            bits.append("fed_by=" + "; ".join(fed_by[:6]))
        if feeds:
            bits.append("feeds=" + "; ".join(feeds[:8]))
        if not bits:
            return ""
        return ("EQUIPMENT (verbatim equipment-registry facts — identity/labelling hints for THIS meter; "
                "aka is a display alias, the canonical asset name stays the data key): " + " | ".join(bits))
    except Exception:
        return ""


def breaker_line(asset):
    """'BREAKER (…): rating_a=… | type=…' or '' (no breaker row / NULL rating / dup twin / knob off / outage)."""
    tbl = _table(asset)
    if not (tbl and _enabled()):
        return ""
    try:
        from data.equipment.ratings import breaker_rating
        r = breaker_rating(tbl)
        if not r or r.get("rating_a") is None:
            return ""
        bt = (r.get("breaker_type") or "").strip()
        return (f"BREAKER (this feeder's real breaker row): rating_a={r['rating_a']:g} A"
                + (f" | type={bt}" if bt else "")
                + " — the overload denominator: a loading/overload claim grounds on THIS rating "
                  "(the breakerOverloadPct fn), never a guessed rating.")
    except Exception:
        return ""


def rtm_bands_line(asset):
    """'RTM STATUS BANDS (…): metric low_max=… normal_max=… …' or ''. Band boundaries are REAL DB consts
    (cmd_catalog consts.rtm_<panel_type>_<metric>_<band>) — R10-legal const sources when cited verbatim."""
    tbl = _table(asset)
    if not (tbl and _enabled()):
        return ""
    try:
        from data.equipment.ratings import rtm_bands_for_asset
        got = rtm_bands_for_asset(tbl)
        bands = (got or {}).get("bands") or {}
        if not bands:
            return ""
        pt = got.get("panel_type") or "-"
        parts = []
        for metric in sorted(bands):
            b = bands[metric] or {}
            seg = " ".join(f"{k}={b[k]:g}" for k in ("low_max", "normal_max", "moderate_max", "high_max")
                           if isinstance(b.get(k), (int, float)))
            if seg:
                parts.append(f"{metric}: {seg}")
        if not parts:
            return ""
        return (f"RTM STATUS BANDS ({got.get('provenance')}, panel_type={pt}; stored as cmd_catalog "
                f"consts.rtm_{pt}_<metric>_<band> rows — a band boundary quoted VERBATIM from here is a LEGAL "
                f"const source per R10 and may ground a threshold morph declared in _morphed): "
                + " | ".join(parts))
    except Exception:
        return ""


def energy_register_line(asset):
    """'ENERGY REGISTER (…): energy_direction=… | energy_scale=… | power_scale=…' + the never-rescale clause, or ''."""
    tbl = _table(asset)
    if not (tbl and _enabled()):
        return ""
    try:
        from data.equipment import bridge as _b
        row = _b.eq_row_for_table(tbl)
        if not row:
            return ""
        bits = []
        d = (row.get("energy_direction") or "").strip() if isinstance(row.get("energy_direction"), str) else None
        if d:
            bits.append(f"energy_direction={d}")
        for k in ("energy_scale", "power_scale"):
            v = row.get(k)
            if v not in (None, "", "1", 1, 1.0):               # scale=1 is the no-op default — pure noise
                bits.append(f"{k}={v}")
        if not bits:
            return ""
        return ("ENERGY REGISTER (equipment registry, VERBATIM — FACTS ONLY): " + " | ".join(bits)
                + " — NEVER rescale/multiply a reading by these; bind columns as-is (reversed-CT energy is the "
                  "executor's register-pair pick, not a scale factor).")
    except Exception:
        return ""


def equipment_fact_lines(asset):
    """The additive equipment fact lines for the user message, in a fixed order — () when the knob is off or
    nothing resolves (byte-identical prompt to pre-wiring). Never raises."""
    if not _enabled():
        return ()
    try:
        return tuple(x for x in (equipment_line(asset), breaker_line(asset),
                                 rtm_bands_line(asset), energy_register_line(asset)) if x)
    except Exception:
        return ()


def member_suffix(member_table):
    """Per-member ' | aka=… | breaker_a=… | load_profile=…' suffix for a PANEL MEMBERS line ('' on miss/knob-off).
    Canonical member name stays FIRST on the line — this only appends display/grounding hints."""
    if not (member_table and _enabled()):
        return ""
    try:
        from data.equipment import bridge as _b
        bits = []
        row = _b.eq_row_for_table(member_table)
        if row:
            aka = (row.get("name") or "").strip()
            if aka:
                bits.append(f"aka={aka}")
            lp = (row.get("load_profile") or "").strip() if isinstance(row.get("load_profile"), str) else None
            if lp:
                bits.append(f"load_profile={lp}")
        try:
            from data.equipment.ratings import breaker_rating
            r = breaker_rating(member_table)
            if r and r.get("rating_a") is not None:
                bits.append(f"breaker_a={r['rating_a']:g}")
        except Exception:
            pass
        return (" | " + " | ".join(bits)) if bits else ""
    except Exception:
        return ""
