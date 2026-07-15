import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# STRUCTURAL OBS ISOLATION [audit 2026-07-14, 03]: point every telemetry WRITER (obs/paths.py door) at a session
# tmpdir BEFORE any obs import, so pytest telemetry — including harness-minted real-shaped rids and subprocesses,
# which inherit env — never lands in the prod outputs/logs sink the admin console serves. setdefault lets an
# orchestrator pre-pin a dir; the OS tmp reaper owns cleanup.
_OBS_TMP = os.environ.setdefault("V48_OBS_DIR", tempfile.mkdtemp(prefix="v48-obs-pytest-"))
os.environ.setdefault("V48_OBS_NOTES_DIR", os.path.join(_OBS_TMP, "notes"))

# `layer2` is ALSO a package at the grandparent backend/layer2/, and pytest prepends `backend` to
# sys.path[0] — shadowing our package. While ROOT is first here, pin `layer2` -> pipeline_v48/layer2
# in sys.modules so every later `import layer2.*` binds to THIS pipeline regardless of path order.
for _m in [m for m in list(sys.modules) if m == "layer2" or m.startswith("layer2.")]:
    _f = getattr(sys.modules[_m], "__file__", "") or ""
    if not os.path.abspath(_f).startswith(ROOT):
        del sys.modules[_m]
import layer2 as _layer2  # noqa: E402  (cache the correct package now, while ROOT is sys.path[0])
assert os.path.abspath(_layer2.__file__).startswith(ROOT), _layer2.__file__

import obs.ai_log as _ai  # noqa: E402  (install the LLM logger early)

_ai.set_run_id("pytest")

# HERMETIC OBS [trace layer]: tests exercise the real trace/span machinery (console + per-trace jsonl), but must
# never write trace rows into the PRODUCTION cmd_catalog obs_* store — stub the pg sink's enqueue for the whole
# session. test_obs_trace.py additionally gates per-test via the bus knob monkeypatch.
import obs.sink_pg as _sink_pg  # noqa: E402

_sink_pg.write = lambda event: None


def pytest_configure(config):
    config.addinivalue_line("markers", "live: exercises a live Qwen call (tolerant of fail-open)")


import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_config_caches():
    """Determinism: config.app_config.cfg + config.vocab.vocab are lru_cache'd process-wide. A test that monkeypatches
    a row/vocab (or the underlying loader) leaves the cache dirty for the NEXT test — which is why
    test_slot_catalog_series passed alone but failed in the full run (a prior test had poisoned the vocab cache). Clear
    both caches before AND after every test so ordering never changes an outcome.

    ALSO re-pin the obs run id per test: run/harness.py overwrites it with r_<sha1(prompt)> during any
    pipeline-exercising test and nothing reset it, so every LATER test's failure/ai records leaked into that
    real-shaped failures_r_*.jsonl — ~24% of the admin console's "real failures" were pytest artifacts
    (over_budget/no_json/truncated/transport were 100% test noise; console_validation/failures.md 2026-07-12)."""
    from config import app_config as _ac, vocab as _vc
    from data import value_probe as _vp
    _ac._load.cache_clear(); _vc.vocab.cache_clear()
    # value_probe's module-level TTL caches (incl. the schema-existence set) outlive a test (TTL 120s) — a stubbed
    # q() that answered the information_schema probe would filter the NEXT test's fake tables. Same isolation rule.
    _vp._CACHE.clear(); _vp._VAL_CACHE.clear(); _vp._EXIST_CACHE.clear()
    _ai.set_run_id("pytest")
    yield
    _ac._load.cache_clear(); _vc.vocab.cache_clear()
    _vp._CACHE.clear(); _vp._VAL_CACHE.clear(); _vp._EXIST_CACHE.clear()
    _ai.set_run_id("pytest")
