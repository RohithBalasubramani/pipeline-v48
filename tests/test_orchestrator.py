"""Orchestrator — 1a ∥ 1b fire in parallel, join with error isolation. [run/harness]"""
import time

from run.parallel import run_parallel
from run.run_id import make_run_id
from run.harness import run_pipeline


def test_run_parallel_isolates_failure():
    def boom():
        raise ValueError("x")
    res = run_parallel({"a": lambda: 1, "b": boom})
    assert res["a"] == 1 and isinstance(res["b"], ValueError)   # one failing doesn't sink the other


def test_run_parallel_is_concurrent():
    def slow():
        time.sleep(0.4); return 1
    t = time.time()
    run_parallel({"a": slow, "b": slow})
    assert time.time() - t < 0.7                                 # ~0.4s (parallel), not ~0.8s (serial)


def test_run_id_stable():
    assert make_run_id("p") == make_run_id("p") and make_run_id("p").startswith("r_")


def test_pipeline_live_join():
    out = run_pipeline("voltage and current health for AHU-5")
    assert out["errors"] == {}
    assert out["layer1a"]["page_key"] == "individual-feeder-meter-shell/voltage-current"
    assert out["layer1b"]["how"] == "AI" and out["layer1b"]["asset"]["mfm_id"] == 36   # GIC-03-N6-AHU-5 (app_devices/gic)
