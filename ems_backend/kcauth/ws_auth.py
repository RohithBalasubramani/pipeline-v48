"""WebSocket (Channels) authentication — port of LoggerFast's ws_auth.py.

Provides two ways to enforce, pick one:

  1. KeycloakWsAuthMiddleware — wrap the URLRouter in backend/asgi.py:

        from kcauth.ws_auth import KeycloakWsAuthMiddleware
        'websocket': KeycloakWsAuthMiddleware(URLRouter(lt_panels_ws + assets_ws)),

     Rejects the handshake (close 1008) unless the connection carries a
     valid Keycloak JWT with the logger-read role. Validated claims land
     on scope['keycloak'].

  2. authenticate_scope(scope) — call from inside a consumer's connect()
     for per-consumer control (mirrors LoggerFast's ws_accept_or_reject):

        claims = await authenticate_scope(self.scope)
        if claims is None:
            await self.close(code=1008); return

Token is read from the Authorization header, else the ?token= query param.

NOTE: not wired into asgi.py by default so existing unauthenticated WS
clients keep working. Enable when the frontend sends tokens.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from urllib.parse import parse_qs

from channels.db import database_sync_to_async

from .permissions import has_logger_read_role
from .security import decode_jwt

log = logging.getLogger(__name__)


def _extract_token(scope: Dict[str, Any]) -> Optional[str]:
    # 1. Authorization header (headers is a list of (bytes, bytes) tuples)
    for key, value in scope.get("headers") or []:
        if key == b"authorization":
            header = value.decode("utf-8", errors="ignore")
            if header.lower().startswith("bearer "):
                return header.split(" ", 1)[1].strip() or None
    # 2. ?token= query parameter
    query_str = (scope.get("query_string") or b"").decode("utf-8", errors="ignore")
    token_list = parse_qs(query_str).get("token")
    if token_list:
        return token_list[0] or None
    return None


@database_sync_to_async
def _validate(token: str) -> Optional[Dict[str, Any]]:
    try:
        claims = decode_jwt(token)
    except Exception as e:  # noqa: BLE001
        log.warning("WebSocket auth: JWT validation failed: %s", e)
        return None
    if not has_logger_read_role(claims):
        log.warning("WebSocket auth: missing logger-read role")
        return None
    return claims


async def authenticate_scope(scope: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Validate a WS connection's token. Returns claims dict or None."""
    token = _extract_token(scope)
    if not token:
        log.warning("WebSocket auth: no token provided")
        return None
    return await _validate(token)


class KeycloakWsAuthMiddleware:
    """Channels middleware: reject WS handshakes lacking a valid Keycloak
    JWT with the logger-read role; stash claims on scope['keycloak']."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "websocket":
            claims = await authenticate_scope(scope)
            if claims is None:
                await send({"type": "websocket.close", "code": 1008})
                return
            scope = dict(scope)
            scope["keycloak"] = claims
        return await self.app(scope, receive, send)
