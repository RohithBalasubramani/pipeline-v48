"""lib/api_auth.py — the ONE shared-secret gate for the V48 HTTP surfaces (host :8770, admin :8790). [R6 partial]

DEFAULT-OFF: the DB knob `api.token` (cmd_catalog.app_config, declared by db/seed_api_token.sql) is unset/empty
today, so require_token() is always True and every request flows exactly as before. When an operator sets a
non-empty value, each request must carry a matching X-V48-Token header or the server responds 401 early.

Read LAZILY per request (cfg is DB-tunable — editing the row takes effect on the next request, no restart) and
fail-OPEN: a config-read error can never lock out the API. Constant-time compare (hmac.compare_digest)."""
import hmac

TOKEN_HEADER = "X-V48-Token"


def require_token(headers):
    """True → let the request through. `headers` is the BaseHTTPRequestHandler .headers mapping (case-insensitive
    lookup). Empty/missing api.token knob = auth DISABLED (today's behavior, byte-identical). Never raises."""
    try:
        from config.app_config import cfg
        token = str(cfg("api.token", "") or "").strip()
        if not token:
            return True
        sent = str((headers.get(TOKEN_HEADER) if headers is not None else None) or "")
        return hmac.compare_digest(sent, token)
    except Exception:
        return True
