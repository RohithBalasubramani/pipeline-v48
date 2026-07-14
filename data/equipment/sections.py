"""data/equipment/sections.py — BUS-SECTION attribution for panel members (equipment.mfm.section), behind the ONE
equipment door. A PCC panel is physically TWO bus sections (A/B, coupler-tied); the registry has ONE canonical row per
panel, but users address sections directly ('pcc-1a' vs 'pcc-1b' — pcc_panel_alias.section marks which). equipment.mfm
carries each member meter's section token ('1A'/'1B'/…/'HT'; bare '1' = common/bus-level gear serving both sections).

`section_of(table)` → that member's section token (None when unmapped). `token(panel_name, 'A')` → the panel's section
token ('PCC-Panel-1','B') → '1B' — REGISTRY-VALIDATED (T0-5): the synthesized token must be a REAL equipment.mfm
section value; both the as-written ('01A') and zero-stripped ('1A') spellings are candidates and exactly ONE registry
hit wins. Zero hits (no such section) or an ambiguous pair (both '01A' and '1A' real) → honest None — never a token
that silently filters the member roll-up to zero. Equipment door dark (empty map) → the legacy synthesized token, so
an outage keeps the fail-open full-view behavior unchanged. A SECTION VIEW keeps ONLY exact-token members: common
('1') and unmapped members stay in the FULL panel view only — including them in a section (or both sections of a
compare) would double-count bus-level gear. Fail-open: any DB failure → {} → no filtering (the full panel view,
never a crash). [atomic; single door]"""
from __future__ import annotations

import re
import threading

_LOCK = threading.Lock()
_CACHE: dict = {}          # {"map": {table: section}} — process-cached; never caches a partial read


def _section_map() -> dict:
    with _LOCK:
        hit = _CACHE.get("map")
        if hit is not None:
            return hit
        try:
            from data.db_client import q
            built = {}
            for tbl, sec in q("cmd_catalog",
                              "SELECT table_name, section FROM equipment.mfm "
                              "WHERE table_name IS NOT NULL AND section IS NOT NULL"):
                if tbl and sec:
                    built[str(tbl)] = str(sec).strip().upper()
            _CACHE["map"] = built                          # publish only after the FULL read succeeded
            return built
        except Exception:
            return {}                                      # fail-open, uncached → self-heals next call


def section_of(table: str) -> str | None:
    """The member meter's section token ('1A'/'2B'/'HT'/…) or None when unmapped / equipment door dark."""
    if not table:
        return None
    return _section_map().get(str(table))


def token(panel_name: str, section: str) -> str | None:
    """('PCC-Panel-1', 'A'|'B') → '1A'/'1B' — the equipment.mfm section token for that panel's bus section,
    REGISTRY-VALIDATED: the as-written ('01A') and zero-stripped ('1A') candidates are checked against the real
    section values in equipment.mfm and the single hit wins. None when the panel name carries no number, the section
    letter is missing, no candidate is a real section, or the pair is ambiguous (both spellings real) — honest
    degrade, never a token that silently filters to zero members. Equipment door dark (empty map) → the legacy
    synthesized token (fail-open on outage, unchanged)."""
    m = re.search(r"(\d+)\s*$", str(panel_name or "").strip())
    s = str(section or "").strip().upper()
    if not m or s not in ("A", "B"):
        return None
    digits = m.group(1)
    real = set(_section_map().values())
    if not real:
        return f"{int(digits)}{s}"                     # equipment door dark → legacy fail-open token
    candidates = {f"{digits}{s}", f"{int(digits)}{s}"}  # as-written + zero-stripped spellings
    hits = candidates & real
    return next(iter(hits)) if len(hits) == 1 else None
