# FILE: rms_backend/settings.py
"""
Django settings for rms_backend project.

This file now serves as a compatibility layer that imports from the
new settings package structure. The actual settings are organized in:
- settings/base.py: Common settings
- settings/development.py: Development environment
- settings/staging.py: Staging environment
- settings/production.py: Production environment

Settings are automatically loaded based on the ENVIRONMENT variable.
"""

import warnings

# Show deprecation warning
warnings.warn(
    "Importing from rms_backend.settings is deprecated. "
    "Use rms_backend.settings.development, rms_backend.settings.staging, "
    "or rms_backend.settings.production instead.",
    DeprecationWarning,
    stacklevel=2
)

# Import from the new settings package
try:
    from .settings import *  # noqa: F401,F403
except ImportError:
    # Fallback for backwards compatibility
    from .settings.development import *  # noqa: F401,F403
    print("⚠️  Loaded development settings as fallback")

# --------------------------------------------------------------------
# Post-import hardening: CORS/CSRF/cookies + ensure our cart middleware is wired.
# --------------------------------------------------------------------

def _ensure(item: str, into: list[str]):
    if item not in into:
        into.append(item)

# Apps
_ensure("corsheaders", INSTALLED_APPS)

# Middleware (order matters)
# Put CORS early
if "corsheaders.middleware.CorsMiddleware" not in MIDDLEWARE:
    MIDDLEWARE.insert(0, "corsheaders.middleware.CorsMiddleware")

# Ensure core middlewares are present
for mw in [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
]:
    _ensure(mw, MIDDLEWARE)

# Ensure our cart middleware is after AuthenticationMiddleware
cart_mw = "orders.middleware.EnsureCartInitializedMiddleware"
if cart_mw not in MIDDLEWARE:
    try:
        idx = MIDDLEWARE.index("django.contrib.auth.middleware.AuthenticationMiddleware")
        MIDDLEWARE.insert(idx + 1, cart_mw)
    except ValueError:
        MIDDLEWARE.append(cart_mw)

# ---------- CORS / CSRF ----------
CORS_ALLOWED_ORIGINS = list(set(
    globals().get("CORS_ALLOWED_ORIGINS", []) + [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        # "https://your-frontend-domain.com",
    ]
))
CORS_ALLOW_CREDENTIALS = True

CSRF_TRUSTED_ORIGINS = list(set(
    globals().get("CSRF_TRUSTED_ORIGINS", []) + [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        # "https://your-frontend-domain.com",
    ]
))

# ---------- Cookies (session must persist across pages) ----------
if DEBUG:
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SAMESITE = "Lax"
    CSRF_COOKIE_SECURE = False
else:
    # If your frontend is on a separate domain over HTTPS, allow cross-site cookies
    SESSION_COOKIE_SAMESITE = "None"
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SAMESITE = "None"
    CSRF_COOKIE_SECURE = True

# Optional: unify cookie name to avoid collisions
SESSION_COOKIE_NAME = globals().get("SESSION_COOKIE_NAME", "rms_sessionid")
# Optional: if API/app use subdomains, set a shared domain in production
# SESSION_COOKIE_DOMAIN = ".example.com"

# ---------- Sticky cart cookie (used by EnsureCartInitializedMiddleware) ----------
CART_COOKIE_NAME = globals().get("CART_COOKIE_NAME", "rms_cart_uuid")
CART_COOKIE_SALT = globals().get("CART_COOKIE_SALT", "rms.cart.cookie.v1")
CART_COOKIE_MAX_AGE = globals().get("CART_COOKIE_MAX_AGE", 60 * 60 * 24 * 30)  # 30 days
