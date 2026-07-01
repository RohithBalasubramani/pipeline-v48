"""run/parallel.py — the one concurrency primitive: run thunks in threads, join, preserve order/exceptions. [orchestrator]"""
from concurrent.futures import ThreadPoolExecutor


def run_parallel(named_thunks):
    """named_thunks: {name: callable() }. Returns {name: result|Exception}. Never raises (fail-isolated)."""
    out = {}
    with ThreadPoolExecutor(max_workers=max(2, len(named_thunks))) as ex:
        futs = {name: ex.submit(fn) for name, fn in named_thunks.items()}
        for name, fut in futs.items():
            try:
                out[name] = fut.result()
            except Exception as e:   # one layer failing must not sink the other
                out[name] = e
    return out
