"""admin/server.py — the admin console HTTP surface. Stdlib only (mirrors host/server.py). Run from anywhere:

    python3 admin/server.py           # binds 0.0.0.0:8790 (env V48_ADMIN_PORT)

Read-only over the run artifacts (admin/README.md lists every endpoint) + POST /admin/api/replay which re-fires a
prompt at the live host API. All responses JSON with open CORS (the Vite dev server proxies /admin/api → here)."""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from admin import ai_usage, assets_log, coverage, explorer, failures_report        # noqa: E402
from admin import latency, replay, runs, search, sql_report, store, trace, validation_log  # noqa: E402
from admin.config import LOGS_DIR, PORT, RUN_ID_RE, window_params                  # noqa: E402


def _first(qs, key, default=None):
    v = (qs.get(key) or [default])[0]
    return v if v not in ("", None) else default


def _int(qs, key, default):
    try:
        return int(_first(qs, key, default))
    except (TypeError, ValueError):
        return default


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, obj, raw=None, content_type="application/json"):
        body = raw if raw is not None else json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):                    # quieter logs
        sys.stderr.write(f"  [admin] {self.command} {self.path}\n")

    def do_OPTIONS(self):
        self._send(204, {})

    def do_GET(self):
        try:
            self._route_get()
        except BrokenPipeError:
            pass
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._send(500, {"ok": False, "error": str(e)[:300]})

    def _route_get(self):
        u = urlparse(self.path)
        qs = parse_qs(u.query)
        path = u.path.rstrip("/")
        t_from, t_to = window_params(qs)

        if path == "/admin/api/health":
            return self._send(200, {"ok": True, "logs_dir": LOGS_DIR, "n_runs": len(store.run_ids())})

        if path == "/admin/api/runs":
            out = runs.list_runs(t_from, t_to, q=_first(qs, "q"), page_key=_first(qs, "page_key"),
                                 limit=_int(qs, "limit", 50), offset=_int(qs, "offset", 0),
                                 sink=_first(qs, "sink", "real"))
            return self._send(200, {"ok": True, **out})

        # /admin/api/run/<rid>[/ai/<idx>|/response]
        if path.startswith("/admin/api/run/"):
            parts = [p for p in path.split("/") if p][2:]          # after admin/api
            rid = parts[1] if len(parts) > 1 else None
            if not rid or not (RUN_ID_RE.match(rid) or rid in ("default", "pytest") or rid.startswith("r_")):
                return self._send(400, {"ok": False, "error": "bad run id"})
            if len(parts) == 2:
                t = trace.build(rid)
                return self._send(200, {"ok": True, "trace": t}) if t else \
                    self._send(404, {"ok": False, "error": f"no artifacts for {rid}"})
            if len(parts) == 4 and parts[2] == "ai":
                call = trace.ai_call_detail(rid, _int({"i": [parts[3]]}, "i", -1))
                return self._send(200, {"ok": True, "call": call}) if call else \
                    self._send(404, {"ok": False, "error": "no such call"})
            if len(parts) == 3 and parts[2] == "response":
                raw = trace.raw_response(rid)
                return self._send(200, None, raw=raw) if raw else \
                    self._send(404, {"ok": False, "error": "no response doc"})
            return self._send(404, {"ok": False, "error": "unknown trace path"})

        if path == "/admin/api/explorer":
            return self._send(200, {"ok": True, **explorer.report(t_from, t_to)})

        if path == "/admin/api/coverage":
            return self._send(200, {"ok": True, **coverage.report(t_from, t_to, page_key=_first(qs, "page_key"))})

        if path == "/admin/api/latency":
            return self._send(200, {"ok": True, **latency.report(t_from, t_to)})

        if path == "/admin/api/failures":
            return self._send(200, {"ok": True, **failures_report.report(
                t_from, t_to, reason=_first(qs, "reason"), stage=_first(qs, "stage"),
                q=_first(qs, "q"), limit=_int(qs, "limit", 100))})

        if path == "/admin/api/ai-usage":
            return self._send(200, {"ok": True, **ai_usage.report(t_from, t_to)})

        if path == "/admin/api/sql":
            slow = _first(qs, "slow_ms")
            return self._send(200, {"ok": True, **sql_report.report(
                t_from, t_to, run_id=_first(qs, "run_id"), q=_first(qs, "q"),
                source=_first(qs, "source"), slow_ms=(float(slow) if slow else None),
                limit=_int(qs, "limit", 100))})

        if path == "/admin/api/assets-log":
            return self._send(200, {"ok": True, **assets_log.report(
                t_from, t_to, how=_first(qs, "how"), q=_first(qs, "q"), limit=_int(qs, "limit", 200))})

        if path == "/admin/api/validation":
            return self._send(200, {"ok": True, "runs": validation_log.run_rows(t_from, t_to),
                                    "sessions": validation_log.sessions()})

        if path == "/admin/api/search/prompts":
            return self._send(200, {"ok": True, "runs": search.prompts(
                _first(qs, "q", ""), t_from, t_to, limit=_int(qs, "limit", 50))})

        if path == "/admin/api/search/errors":
            out = failures_report.report(t_from, t_to, reason=_first(qs, "reason"),
                                         stage=_first(qs, "stage"), q=_first(qs, "q"),
                                         limit=_int(qs, "limit", 100))
            return self._send(200, {"ok": True, "total": out["total"], "hits": out["recent"],
                                    "by_reason": out["by_reason"]})

        if path == "/admin/api/replays":
            return self._send(200, {"ok": True, "replays": replay.listing()})

        return self._send(404, {"ok": False, "error": "unknown endpoint"})

    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n) or b"{}") if n else {}
        except (ValueError, TypeError):
            return self._send(400, {"ok": False, "error": "bad JSON body"})
        u = urlparse(self.path)
        if u.path.rstrip("/") == "/admin/api/replay":
            out = replay.launch(body.get("prompt"), asset_id=body.get("asset_id"),
                                asset_ids=body.get("asset_ids"), date_window=body.get("date_window"))
            return self._send(200 if out.get("launched") else 400, out)
        return self._send(404, {"ok": False, "error": "unknown endpoint"})


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = 64


def main():
    srv = _Server(("0.0.0.0", PORT), Handler)
    print(f"admin console API on 0.0.0.0:{PORT} (logs: {LOGS_DIR})", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
