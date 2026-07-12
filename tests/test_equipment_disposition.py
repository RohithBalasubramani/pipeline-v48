"""stream E — equipment-wiring structural invariants.

SINGLE DOOR: every SQL read of the `equipment` schema lives in data/equipment/*.py (the one fail-open door), the
idempotent db/seed_equipment_*.sql seeds, or the tests themselves. Any other module reaching into `FROM equipment.`
bypasses the bridge's dup-table / identity gates — exactly the id-space fabrication path the wiring was designed to
make impossible.

KNOB MIRRORS: every equipment.* app_config knob the code reads has a code-default fallback (DB-down never crashes).
"""
import os
import re

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DOOR = re.compile(r"(?i)(from|join)\s+equipment\.")
_ALLOWED = ("data/equipment/", "db/seed_equipment_", "tests/test_equipment_")
_SKIP_DIRS = ("__pycache__", "node_modules", ".git", "host/web", "outputs", ".playwright")


def _files():
    for dp, dns, fns in os.walk(_ROOT):
        rel_dp = os.path.relpath(dp, _ROOT)
        if any(s in rel_dp + "/" for s in _SKIP_DIRS):
            dns[:] = []
            continue
        for f in fns:
            if f.endswith((".py", ".sql")):
                yield os.path.join(rel_dp, f).replace("\\", "/").lstrip("./")


def test_equipment_schema_single_door():
    offenders = []
    for rel in _files():
        if any(rel.startswith(a) or ("/" + a) in ("/" + rel) for a in _ALLOWED):
            continue
        try:
            txt = open(os.path.join(_ROOT, rel), errors="replace").read()
        except OSError:
            continue
        if _DOOR.search(txt):
            offenders.append(rel)
    assert offenders == [], f"equipment-schema reads outside the data/equipment door: {offenders}"


def test_equipment_knobs_have_code_default_mirrors():
    """Each knob read site passes an explicit code default — grep-level proof the DB-down path is defined.
    equipment_facts reads via flag_on (THE boolean-knob vocabulary, D6 2026-07-12) with its default-on preserved."""
    reads = {
        "layer2/emit/equipment_facts.py": 'flag_on("equipment.facts.enabled", True)',
        "layer1b/resolve/asset_candidates.py": 'cfg("equipment.alias.enabled", "on")',
    }
    for rel, needle in reads.items():
        txt = open(os.path.join(_ROOT, rel), errors="replace").read()
        assert needle in txt, f"{rel} must read its knob with an explicit code default: {needle}"
