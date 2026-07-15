"""data/registry/feeder_class.py — the FEEDER-CLASS fact for a member meter (registry_feeder_class.feeder_class),
behind the ONE fail-open door. member_registry_facts restores type_code/load_group, but lt_mfm_type carries only 4
codes (apfc, lt_panel, transformer, ups) — so bpdb/hhf/incomer/spare/dg/ahu feeders have NO type-code and can only be
discriminated by the fragile name_contains. feeder_class is the token-derived fact that fixes that: one class per meter
table, seeded (idempotent) by scripts/seed_feeder_class.py, read here for the roster matchers' feeder_classes any-of.

`feeder_class_of(table)` → that meter's feeder class ('ups'/'bpdb'/'solar-incomer'/… lowercased) or None when the
table is unmapped / the door is dark. Process-cached after ONE full read (never caches a partial); ANY DB error /
outage → {} → no attribution (honest None, self-heals next call), never a crash. EXACTLY the data/equipment/sections.py
accessor pattern. [atomic; single door]"""
from __future__ import annotations

import threading

_LOCK = threading.Lock()
_CACHE: dict = {}          # {"map": {table: feeder_class}} — process-cached; never caches a partial read


def _feeder_map() -> dict:
    with _LOCK:
        hit = _CACHE.get("map")
        if hit is not None:
            return hit
        try:
            from data.db_client import q
            built = {}
            for tbl, fc in q("cmd_catalog",
                             "SELECT table_name, feeder_class FROM registry_feeder_class "
                             "WHERE table_name IS NOT NULL AND feeder_class IS NOT NULL"):
                if tbl and fc:
                    built[str(tbl)] = str(fc).strip().lower()
            _CACHE["map"] = built                          # publish only after the FULL read succeeded
            return built
        except Exception:
            return {}                                      # fail-open, uncached → self-heals next call


def feeder_class_of(table: str) -> str | None:
    """The member meter's feeder class ('ups'/'bpdb'/'hhf'/'solar-incomer'/…) or None when unmapped / door dark."""
    if not table:
        return None
    return _feeder_map().get(str(table))
