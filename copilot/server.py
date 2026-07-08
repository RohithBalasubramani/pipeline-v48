"""EMS Query Copilot — standalone HTTP service (port :8772).

Fully self-contained: stdlib http.server only, no pipeline imports. Serves
  GET  /                 -> the standalone demo page (frontend/demo.html)
  GET  /copilot/health   -> {ok, model_up, index_entities}
  POST /copilot/suggest  -> {autofill, ghost, suggestions, source, latency_ms}

Run:  python3 server.py        (or via deploy/ems-copilot.service)
"""
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import generate
import llm
import retrieve
import starters
from config import PORT

HERE = os.path.dirname(os.path.abspath(__file__))
DEMO = os.path.join(HERE, "frontend", "demo.html")

_cache = {}
_CACHE_MAX = 1024
_lock = threading.Lock()


def suggest(text):
    key = (text or "").strip()
    with _lock:
        hit = _cache.get(key)
    if hit is not None:
        return {**hit, "cached": True}
    t0 = time.time()
    g = retrieve.retrieve(text)
    out = generate.generate(text, g)
    out["latency_ms"] = int((time.time() - t0) * 1000)
    out["cached"] = False
    # Cache ONLY a genuine model result. NEVER cache an 'unavailable'/error response: otherwise a transient
    # model-endpoint outage (:8201 down / connection refused) poisons the cache with a permanent failure that
    # survives every later query until a process restart. Skipping failures makes the copilot self-heal — the next
    # query re-attempts the model the moment it is back, and a stale outage response can never be replayed.
    if out.get("source") == "model" and not out.get("error"):
        with _lock:
            if len(_cache) > _CACHE_MAX:
                _cache.clear()
            _cache[key] = out
    return out


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self._send(204, b"")

    def do_GET(self):
        if self.path.startswith("/copilot/health"):
            ix = retrieve.index()
            return self._send(200, {"ok": True, "model_up": llm.is_up(),
                                    "index_entities": len(ix.ents)})
        if self.path.startswith("/copilot/starters"):
            try:
                return self._send(200, {"starters": starters.starters()})
            except Exception as e:
                return self._send(200, {"starters": [], "error": str(e)[:160]})
        if self.path == "/" or self.path.startswith("/index"):
            try:
                with open(DEMO, "rb") as f:
                    return self._send(200, f.read(), "text/html; charset=utf-8")
            except FileNotFoundError:
                return self._send(404, {"error": "demo.html not found"})
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        if not self.path.startswith("/copilot/suggest"):
            return self._send(404, {"error": "not found"})
        try:
            n = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(n) or b"{}")
            text = payload.get("text", "")
        except Exception as e:
            return self._send(400, {"error": f"bad request: {e}"})
        try:
            return self._send(200, suggest(text))
        except Exception as e:
            return self._send(500, {"error": str(e)[:200], "autofill": "", "suggestions": []})

    def log_message(self, *a):
        pass  # quiet


def _warmup():
    """Compile the JSON grammar + CUDA graphs before real traffic."""
    try:
        retrieve.index()
        generate.generate("show", timeout=30)
        starters.starters()   # pre-generate the empty-state roster so it loads instantly
        print("[copilot] warmup complete; model_up =", llm.is_up(), flush=True)
    except Exception as e:
        print("[copilot] warmup skipped:", str(e)[:120], flush=True)


def main():
    threading.Thread(target=_warmup, daemon=True).start()
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"[copilot] serving on http://0.0.0.0:{PORT}  (demo at /, suggest at POST /copilot/suggest)", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
