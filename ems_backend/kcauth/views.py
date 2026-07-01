"""Public auth endpoints — DRF port of LoggerFast's routers/auth.py.

Faithful copy: register / assign-role / roles management are PUBLIC
(no auth), exactly as LoggerFast (which mirrored the Django AllowAny
original). Mounted under /api/auth/ by backend/urls.py.

  POST   /api/auth/register
  POST   /api/auth/login
  POST   /api/auth/refresh
  POST   /api/auth/assign-role/<username>
  GET    /api/auth/roles/<username>
  POST   /api/auth/roles/<username>     body {"role": "logger_read"|"logger_write"}
  DELETE /api/auth/roles/<username>     body {"role": "logger_read"|"logger_write"}
"""
from __future__ import annotations

from typing import Any, Dict

from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .keycloak_admin import (
    KeycloakAdminError,
    assign_client_role_to_user,
    assign_realm_role_to_user,
    create_user,
    get_client_role,
    get_client_uuid,
    get_realm_role,
    get_service_account_token,
    get_user_id_by_username,
    get_user_realm_roles,
    remove_realm_role_from_user,
    set_user_password,
    user_login,
    user_refresh,
)
from .keycloak_config import KEYCLOAK_ADMIN_CLIENT_ID

LOGGER_ROLES = {"logger_read", "logger_write"}


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def register(request):
    """Create a new user in Keycloak. Public endpoint (no auth required).

    Body: {"username", "email", "password", "first_name", "last_name", "enabled"}
    """
    payload: Dict[str, Any] = request.data or {}
    username = (payload.get("username") or "").strip()
    email = (payload.get("email") or "").strip()
    password = payload.get("password") or ""
    first_name = (payload.get("first_name") or "").strip()
    last_name = (payload.get("last_name") or "").strip()
    enabled = bool(payload.get("enabled", True))

    if not username or not email or not password:
        return Response(
            {"detail": "username, email, and password are required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        token = get_service_account_token()
        user_id = create_user(
            token=token,
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            enabled=enabled,
        )
        set_user_password(token=token, user_id=user_id, password=password, temporary=False)
    except KeycloakAdminError as e:
        return Response(
            {"error": "keycloak_error", "message": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except Exception as e:  # noqa: BLE001
        return Response(
            {"error": "server_error", "message": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return Response({"ok": True, "user_id": user_id, "username": username, "email": email})


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def login(request):
    """Authenticate against Keycloak and return JWT tokens. Public endpoint.

    Body: {"username", "password"}
    """
    payload: Dict[str, Any] = request.data or {}
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""

    if not username or not password:
        return Response(
            {"detail": "username and password are required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        token_data = user_login(username, password)
    except KeycloakAdminError:
        return Response({"detail": "Login failed"}, status=status.HTTP_401_UNAUTHORIZED)
    except Exception as e:  # noqa: BLE001
        return Response(
            {"error": "keycloak_error", "message": str(e)},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    return Response(token_data)


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def refresh(request):
    """Refresh an access token using a refresh_token. Public endpoint.

    Body: {"refresh_token"}
    """
    payload: Dict[str, Any] = request.data or {}
    refresh_token = (payload.get("refresh_token") or "").strip()
    if not refresh_token:
        return Response(
            {"detail": "refresh_token is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        token_data = user_refresh(refresh_token)
    except KeycloakAdminError:
        return Response(
            {"detail": "Token refresh failed — please log in again"},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    except Exception as e:  # noqa: BLE001
        return Response(
            {"error": "keycloak_error", "message": str(e)},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    return Response(token_data)


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def assign_role(request, username: str):
    """Assign the neuract-admin client role to a user. Public endpoint (mirrors Django)."""
    try:
        token = get_service_account_token()

        user_id = get_user_id_by_username(token, username)
        if not user_id:
            return Response({"detail": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        client_uuid = get_client_uuid(token, KEYCLOAK_ADMIN_CLIENT_ID)
        if not client_uuid:
            return Response(
                {"detail": "Keycloak client not found"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        role = get_client_role(token, client_uuid, "neuract-admin")
        if not role:
            return Response({"detail": "Role not found"}, status=status.HTTP_404_NOT_FOUND)

        assign_client_role_to_user(token, user_id, client_uuid, role)
    except KeycloakAdminError as e:
        return Response(
            {"error": "keycloak_error", "message": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        {
            "ok": True,
            "username": username,
            "user_id": user_id,
            "client": KEYCLOAK_ADMIN_CLIENT_ID,
            "role": "neuract-admin",
        }
    )


@api_view(["GET", "POST", "DELETE"])
@authentication_classes([])
@permission_classes([AllowAny])
def roles(request, username: str):
    """Realm role management for a user (logger_read / logger_write).

    GET    -> list the user's realm roles + logger_read/logger_write booleans
    POST   -> assign  {"role": "logger_read"|"logger_write"}
    DELETE -> remove  {"role": "logger_read"|"logger_write"}
    """
    if request.method == "GET":
        try:
            token = get_service_account_token()
            user_id = get_user_id_by_username(token, username)
            if not user_id:
                return Response({"detail": "User not found"}, status=status.HTTP_404_NOT_FOUND)
            user_roles = get_user_realm_roles(token, user_id)
            role_names = [r["name"] for r in user_roles]
        except KeycloakAdminError as e:
            return Response(
                {"error": "keycloak_error", "message": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {
                "username": username,
                "roles": role_names,
                "logger_read": "logger_read" in role_names,
                "logger_write": "logger_write" in role_names,
            }
        )

    # POST / DELETE share the role-name validation + lookup
    payload: Dict[str, Any] = request.data or {}
    role_name = (payload.get("role") or "").strip()
    if role_name not in LOGGER_ROLES:
        return Response(
            {"detail": f"Invalid role '{role_name}'. Must be one of: {', '.join(sorted(LOGGER_ROLES))}"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        token = get_service_account_token()
        user_id = get_user_id_by_username(token, username)
        if not user_id:
            return Response({"detail": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        role_repr = get_realm_role(token, role_name)
        if not role_repr:
            return Response(
                {"detail": f"Realm role '{role_name}' not found in Keycloak"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if request.method == "POST":
            assign_realm_role_to_user(token, user_id, role_repr)
            action = "assigned"
        else:  # DELETE
            remove_realm_role_from_user(token, user_id, role_repr)
            action = "removed"
    except KeycloakAdminError as e:
        return Response(
            {"error": "keycloak_error", "message": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response({"ok": True, "username": username, "role": role_name, "action": action})
