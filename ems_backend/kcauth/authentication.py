"""DRF authentication backed by Keycloak JWTs.

Mirrors LoggerFast's FastAPI `get_claims` dependency, re-expressed as a
DRF `BaseAuthentication`. Token sources (in order):
  1. Authorization: Bearer <token>
  2. X-Agent-Token header (desktop frontend client.js fallback)

Behaviour:
  - No token        -> returns None (anonymous; permission layer decides)
  - Expired token   -> AuthenticationFailed (401, TOKEN_EXPIRED)
  - Invalid token   -> AuthenticationFailed (401, PERMISSION_DENIED)
  - Valid token     -> (KeycloakUser, claims); request.auth == claims dict

`authenticate_header` returns a Bearer challenge so DRF answers 401 (not
403) when a protected view is hit without credentials.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

import jwt
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from .security import decode_jwt, extract_bearer_token

log = logging.getLogger(__name__)


class KeycloakUser:
    """Lightweight request.user wrapper around validated JWT claims.

    Quacks like an authenticated Django user enough for DRF/templates
    (`is_authenticated`) without touching the ORM `auth.User` table.
    """

    is_authenticated = True
    is_active = True
    is_anonymous = False

    def __init__(self, claims: Dict[str, Any]):
        self.claims = claims
        self.username = claims.get("preferred_username") or claims.get("sub") or ""
        self.email = claims.get("email") or ""
        self.sub = claims.get("sub") or ""
        self.roles = (claims.get("realm_access") or {}).get("roles") or []

    def __str__(self) -> str:
        return self.username or "keycloak-user"


class KeycloakAuthentication(BaseAuthentication):
    def authenticate(self, request) -> Optional[Tuple[KeycloakUser, Dict[str, Any]]]:
        token: Optional[str] = extract_bearer_token(request.headers.get("authorization"))

        # Fallback: X-Agent-Token header (used by desktop frontend client.js)
        if not token:
            token = request.headers.get("x-agent-token") or None

        if not token:
            return None  # anonymous — let permission classes / AllowAny decide

        try:
            claims = decode_jwt(token)
        except jwt.ExpiredSignatureError:
            raise AuthenticationFailed(
                {"success": False, "error": "TOKEN_EXPIRED", "message": "Token has expired"}
            )
        except Exception as e:  # noqa: BLE001 — mirror LoggerFast: any failure == invalid
            log.debug("JWT validation failed: %s", e)
            raise AuthenticationFailed(
                {"success": False, "error": "PERMISSION_DENIED", "message": "Invalid token"}
            )

        return KeycloakUser(claims), claims

    def authenticate_header(self, request) -> str:
        return "Bearer realm=cmd"
