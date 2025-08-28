# accounts/urls.py
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView  # optional (kept if used elsewhere)

from .views import (
    whoami,
    SessionLogout,
    SessionLoginJSON,
    RegisterJSON,
    MeView,  # NOTE: this is a FUNCTION-BASED VIEW in your codebase
)

app_name = "accounts"

urlpatterns = [
    # Session-based JSON endpoints for the modal (Django auth + CSRF)
    path("login/", SessionLoginJSON.as_view(), name="login_json"),
    path("register/", RegisterJSON.as_view(), name="register_json"),
    path("logout/", SessionLogout.as_view(), name="logout_json"),

    # Session check + profile
    path("auth/whoami/", whoami, name="whoami"),
    # FIX: MeView is a function, so we must NOT call .as_view()
    path("me/", MeView, name="me"),

    # Optional: keep these if other parts of your stack still need them
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("token/verify/", TokenVerifyView.as_view(), name="token_verify"),

    # Compatibility alias used by some storefront JS for JWT refresh
    path("jwt/refresh/", TokenRefreshView.as_view(), name="jwt_refresh"),
]
