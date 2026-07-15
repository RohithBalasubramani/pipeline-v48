"""sweep/checks/registry_drift.py — CLI wrapper for the registry↔information_schema drift check.

Thin shape-only wrapper (the check core lives in data/registry/drift.py so host boot never imports sweep
internals). The DANGEROUS class is dangling_unmarked: a registry row whose physical table is missing live
while the cmd_catalog mirror still stamps table_exists='t' — the resolver would pin a ghost. Fix = re-run
scripts/sync_neuract_registry.py (never hand-edit either DB). [audit 2026-07-14, 01 F1 permanence]"""
from data.registry.drift import check


def run_registry_drift():
    out = check()
    if "skipped" in out:
        return {"ok": True, "skipped": out["skipped"]}
    return {"ok": not out["dangling_unmarked"],
            "n_dangling_marked": len(out["dangling_marked"]),
            "n_dangling_unmarked": len(out["dangling_unmarked"]),
            **out}
