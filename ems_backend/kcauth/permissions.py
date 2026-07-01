"""DRF permission classes mirroring LoggerFast's FastAPI role dependencies.

  has_logger_read_role / has_logger_write_role  -> claim helpers
  RequireLoggerRead                             -> require_logger_read
  RequireLoggerWrite                            -> require_logger_write
  SafeOrWrite                                   -> require_safe_or_write

Claims are read from `request.auth` (set by KeycloakAuthentication). When
no valid token authenticated the request, `request.auth` is None and the
permission denies; because KeycloakAuthentication defines a Bearer
`authenticate_header`, DRF then returns 401 rather than 403 — matching
LoggerFast's "missing token => 401, wrong role => 403" behaviour.

Both hyphen and underscore role spellings are accepted (logger-read /
logger_read), exactly as LoggerFast did.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from rest_framework.permissions import SAFE_METHODS, BasePermission


def _get_roles(claims: Optional[Dict[str, Any]]) -> List[str]:
    """Extract realm roles from JWT claims."""
    if not claims:
        return []
    return (claims.get("realm_access") or {}).get("roles") or []


def has_logger_read_role(claims: Optional[Dict[str, Any]]) -> bool:
    roles = _get_roles(claims)
    return "logger-read" in roles or "logger_read" in roles


def has_logger_write_role(claims: Optional[Dict[str, Any]]) -> bool:
    roles = _get_roles(claims)
    return "logger-write" in roles or "logger_write" in roles


class RequireLoggerRead(BasePermission):
    """Requires a valid Keycloak JWT carrying the logger-read realm role."""

    message = {"success": False, "error": "INSUFFICIENT_ROLE", "message": "logger-read role required"}

    def has_permission(self, request, view) -> bool:
        return has_logger_read_role(getattr(request, "auth", None))


class RequireLoggerWrite(BasePermission):
    """Requires a valid Keycloak JWT carrying the logger-write realm role."""

    message = {"success": False, "error": "INSUFFICIENT_ROLE", "message": "logger-write role required"}

    def has_permission(self, request, view) -> bool:
        return has_logger_write_role(getattr(request, "auth", None))


class SafeOrWrite(BasePermission):
    """SAFE methods (GET/HEAD/OPTIONS) need a valid token only; UNSAFE
    methods (POST/PUT/PATCH/DELETE) additionally need the logger-write role."""

    message = {
        "success": False,
        "error": "INSUFFICIENT_ROLE",
        "message": "logger-write role required for write operations",
    }

    def has_permission(self, request, view) -> bool:
        claims = getattr(request, "auth", None)
        if not claims:
            return False  # no valid token -> 401 via authenticate_header
        if request.method in SAFE_METHODS:
            return True
        return has_logger_write_role(claims)
