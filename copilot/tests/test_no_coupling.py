"""Guarantee: the copilot layer imports NOTHING from the pipeline (L1/L2/L3).

Scans every .py in ems_copilot for imports of pipeline modules. Run:
    python3 tests/test_no_coupling.py     (exit 0 = clean)
"""
import ast
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# v48 pipeline runtime packages the copilot layer must never import (stays decoupled).
# NOTE: not listing config/llm/db — the copilot has its OWN same-dir config.py / llm.py
# / db.py, so `import config` resolves to the copilot's, not the v48 package.
FORBIDDEN = {
    "layer1a", "layer1b", "layer2", "run", "validate",
    "payload_db", "fe_contract",
    "obs", "host", "grounding", "ems_exec", "registries",
    # refactor-campaign homes (2026-07-12): lib/ shared primitives, domain/ kernel, knowledge Q&A layer;
    # `data` has NO copilot-local twin, so a bare `import data` would silently bind the pipeline package.
    "lib", "domain", "knowledge", "data",
    # retired/moved package names kept defensively (workers/ems_compat/partition/contracts no longer exist at root)
    "workers", "ems_compat", "partition", "contracts",
    # legacy v47 pipeline modules (kept for safety)
    "pipeline", "layer2_swap", "column_resolve", "panel_resolve", "l6", "l6_2",
}


def imported_names(path):
    with open(path, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=path)
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                names.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module.split(".")[0])
    return names


def find_violations():
    # build.py uses the v48 asset resolver via a SUBPROCESS (process boundary, cwd=pipeline_v48),
    # not a Python import — so even it stays import-decoupled and is checked like everything else.
    violations = []
    checked = 0
    for fn in os.listdir(ROOT):
        if not fn.endswith(".py"):
            continue
        checked += 1
        bad = imported_names(os.path.join(ROOT, fn)) & FORBIDDEN
        if bad:
            violations.append((fn, sorted(bad)))
    return violations, checked


def test_no_pipeline_coupling():
    """pytest entry [audit TC-1 2026-07-12]: the guard used to be script-only — `pytest copilot/tests/` collected
    ZERO tests, so a full-suite run silently got no coverage from it. Same check as script mode."""
    violations, checked = find_violations()
    assert checked > 0, f"no copilot modules found under {ROOT}"
    assert not violations, "; ".join(f"COUPLING VIOLATION: {fn} imports {bad}" for fn, bad in violations)


def main():
    violations, checked = find_violations()
    if violations:
        for fn, bad in violations:
            print(f"COUPLING VIOLATION: {fn} imports {bad}")
        sys.exit(1)
    print(f"OK — no pipeline imports across {checked} copilot modules")


if __name__ == "__main__":
    main()
