"""run/parallel.py — the one concurrency primitive: run thunks in threads, join, preserve order/exceptions. [orchestrator]"""
from concurrent.futures import ThreadPoolExecutor


def run_parallel(named_thunks, max_workers=None):
    """named_thunks: {name: callable() }. Returns {name: result|Exception}. Never raises (fail-isolated).

    max_workers CAPS the pool so a fan-out cannot over-subscribe a shared downstream (the vLLM). Default (None) keeps
    the historical behaviour — one worker per thunk (max(2, N)). A caller that fans MANY large-prompt emits at once
    (run_2_all's per-card L2 fan-out) passes a bound so each in-flight emit keeps enough per-request decode throughput
    to finish inside its l2_emit timeout: N concurrent ~22K-tok emits split the vLLM's throughput N ways, so an
    UNBOUNDED 5-card page put the biggest emit (the harmonics heatmap) at the 150s fail-fast edge even solo — a bound
    trades a little page latency for a large per-request timeout margin. Excess thunks queue and run as slots free."""
    n = len(named_thunks)
    if n == 0:
        return {}
    workers = max(2, n) if max_workers is None else max(1, min(n, int(max_workers)))
    out = {}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {name: ex.submit(fn) for name, fn in named_thunks.items()}
        for name, fut in futs.items():
            try:
                out[name] = fut.result()
            except Exception as e:   # one layer failing must not sink the other
                out[name] = e
    return out
