from __future__ import annotations

import json
from typing import Any, Dict

from django.contrib import auth
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.http import HttpRequest, JsonResponse
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST

User = get_user_model()


# -----------------------------------------------------------------------------
# Session helpers
# -----------------------------------------------------------------------------

def _json_body(request: HttpRequest) -> Dict[str, Any]:
    try:
        return json.loads(request.body.decode("utf-8"))
    except Exception:
        return {}


def whoami(request: HttpRequest) -> JsonResponse:
    """
    Lightweight session/CSRF ping used by the storefront JS.
    """
    user = request.user if getattr(request, "user", None) and request.user.is_authenticated else None
    return JsonResponse(
        {
            "ok": True,
            "is_auth": bool(user),
            "user": {"id": user.id, "username": user.get_username()} if user else None,
            "csrf": get_token(request),
        }
    )


# -----------------------------------------------------------------------------
# Session Auth JSON endpoints (kept minimal; align with old ZIP flow)
# -----------------------------------------------------------------------------

@method_decorator(csrf_protect, name="dispatch")
class SessionLoginJSON(View):
    """
    POST { "username": "...", "password": "..." }
    Sets Django session cookie on success (HTTPOnly).
    """
    def post(self, request: HttpRequest):
        data = _json_body(request)
        username = (data.get("username") or "").strip()
        password = (data.get("password") or "").strip()
        if not username or not password:
            return JsonResponse({"detail": "Username and password required."}, status=400)

        user = authenticate(request, username=username, password=password)
        if not user:
            return JsonResponse({"detail": "Invalid credentials."}, status=401)

        login(request, user)

        # If you maintain a server-side cart, merge guest cart here (optional).
        # For now, we only ping back status and a fresh CSRF token.
        return JsonResponse({"ok": True, "user": {"id": user.id, "username": user.get_username()}, "csrf": get_token(request)})


@method_decorator(csrf_protect, name="dispatch")
class RegisterJSON(View):
    """
    POST { "username": "...", "password": "...", "email": "optional" }
    Creates a new user and logs them in.
    """
    def post(self, request: HttpRequest):
        data = _json_body(request)
        username = (data.get("username") or "").strip()
        password = (data.get("password") or "").strip()
        email = (data.get("email") or "").strip()

        if not username or not password:
            return JsonResponse({"detail": "Username and password required."}, status=400)
        if User.objects.filter(username__iexact=username).exists():
            return JsonResponse({"detail": "Username already exists."}, status=400)

        user = User.objects.create_user(username=username, password=password, email=email or None)
        login(request, user)
        return JsonResponse({"ok": True, "user": {"id": user.id, "username": user.get_username()}, "csrf": get_token(request)})


@method_decorator(csrf_protect, name="dispatch")
class SessionLogout(View):
    """
    POST {} — logs out the current user.
    """
    def post(self, request: HttpRequest):
        logout(request)
        return JsonResponse({"ok": True})


@require_GET
def MeView(request: HttpRequest):
    """
    GET current session user info.
    """
    if not (getattr(request, "user", None) and request.user.is_authenticated):
        return JsonResponse({"detail": "Not authenticated."}, status=401)
    user = request.user
    return JsonResponse({"id": user.id, "username": user.get_username(), "email": user.email or ""})
