# rms_backend/settings.py
from __future__ import annotations

import os
from pathlib import Path
from datetime import timedelta
from urllib.parse import urlparse

from dotenv import load_dotenv

# -----------------------------------------------------------------------------
# Paths / env
# -----------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# -----------------------------------------------------------------------------
# Core
# -----------------------------------------------------------------------------
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-not-for-prod")
DEBUG = os.getenv("DJANGO_DEBUG", "1") == "1"

def _split_csv(name: str, default: str = "") -> list[str]:
    raw = os.getenv(name, default) or ""
    return [s.strip() for s in raw.split(",") if s.strip()]

ALLOWED_HOSTS = _split_csv("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost,[::1],testserver")

# Trust same as ALLOWED_HOSTS plus scheme-explicit origins if provided
CSRF_TRUSTED_ORIGINS = _split_csv(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    ",".join([f"http://{h}" for h in ALLOWED_HOSTS] + [f"https://{h}" for h in ALLOWED_HOSTS]),
)

# -----------------------------------------------------------------------------
# Applications
# -----------------------------------------------------------------------------
INSTALLED_APPS = [
    # Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Third-party
    "corsheaders",
    "rest_framework",
    "django_filters",
    "drf_spectacular",

    # Project apps
    "accounts",
    "core",
    "menu",
    "inventory",
    "orders",          # kept if referenced by payments
    "orders_extras",
    "coupons",
    "payments",
    "reservations",
    "loyality",        # spelling matches your folder
    "billing",
    "reports",
    "engagement",
    "storefront",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",  # should be high in the list
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # static in prod
    "django.contrib.sessions.middleware.SessionMiddleware",
    "orders.middleware.EnsureCartInitializedMiddleware",  # Initialize cart for anonymous users
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "rms_backend.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],  # optional project-level
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "rms_backend.wsgi.application"

# -----------------------------------------------------------------------------
# Database
# -----------------------------------------------------------------------------
# Default to SQLite for local; support Postgres via env vars
# Either use DATABASE_URL or discrete PG_ vars.
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

if DATABASE_URL:
    u = urlparse(DATABASE_URL)
    if u.scheme.startswith("postgres"):
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": (u.path or "/")[1:],
                "USER": u.username or "",
                "PASSWORD": u.password or "",
                "HOST": u.hostname or "",
                "PORT": str(u.port or ""),
            }
        }
    else:
        # fallback to sqlite if unknown scheme
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": BASE_DIR / "db.sqlite3",
            }
        }
else:
    PG_NAME = os.getenv("PG_NAME")
    if PG_NAME:
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": PG_NAME,
                "USER": os.getenv("PG_USER", ""),
                "PASSWORD": os.getenv("PG_PASSWORD", ""),
                "HOST": os.getenv("PG_HOST", "127.0.0.1"),
                "PORT": os.getenv("PG_PORT", "5432"),
            }
        }
    else:
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": BASE_DIR / "db.sqlite3",
            }
        }

# -----------------------------------------------------------------------------
# Password validation
# -----------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# -----------------------------------------------------------------------------
# Internationalization
# -----------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kathmandu"
USE_I18N = True
USE_TZ = True

# -----------------------------------------------------------------------------
# Static / Media
# -----------------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"  # collectstatic output for prod
STATICFILES_DIRS = [
    # Removed storefront/static as it's automatically found by AppDirectoriesFinder
]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Django 4.2+/5.x storage settings
STORAGES = {
    # default storage for uploads (media/)
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {
            "location": str(MEDIA_ROOT),
            "base_url": MEDIA_URL,
        },
    },
    # staticfiles storage (served by WhiteNoise in prod)
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

# -----------------------------------------------------------------------------
# REST framework / API
# -----------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_AUTHENTICATION_CLASSES": [
        # Keep both: session for storefront modal, JWT for APIs if you use them
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
    ],
}

SPECTACULAR_SETTINGS = {
    "TITLE": "RMS API",
    "DESCRIPTION": "Restaurant Management System API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# SimpleJWT (if you use JWT flows anywhere)
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(os.getenv("JWT_ACCESS_MINUTES", "30"))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(os.getenv("JWT_REFRESH_DAYS", "7"))),
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# -----------------------------------------------------------------------------
# Sessions / Cookies
# -----------------------------------------------------------------------------
SESSION_COOKIE_AGE = int(os.getenv("SESSION_COOKIE_AGE", str(60 * 60 * 24 * 7)))  # 7 days
SESSION_SAVE_EVERY_REQUEST = True

CSRF_COOKIE_SECURE = os.getenv("CSRF_COOKIE_SECURE", "0") == "1"
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "0") == "1"
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = os.getenv("SECURE_HSTS_INCLUDE_SUBDOMAINS", "0") == "1"
SECURE_HSTS_PRELOAD = os.getenv("SECURE_HSTS_PRELOAD", "0") == "1"
SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "0") == "1"

# -----------------------------------------------------------------------------
# CORS
# -----------------------------------------------------------------------------
CORS_ALLOW_ALL_ORIGINS = os.getenv("CORS_ALLOW_ALL_ORIGINS", "0") == "1"
CORS_ALLOWED_ORIGINS = _split_csv("CORS_ALLOWED_ORIGINS", "")
CORS_ALLOW_CREDENTIALS = True

# -----------------------------------------------------------------------------
# Stripe
# -----------------------------------------------------------------------------
STRIPE_PUBLIC_KEY = os.getenv("STRIPE_PUBLIC_KEY", "")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_CURRENCY = (os.getenv("STRIPE_CURRENCY", "usd") or "usd").lower()

# -----------------------------------------------------------------------------
# Authentication redirects
# -----------------------------------------------------------------------------
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/my-orders/"
LOGOUT_REDIRECT_URL = "/"

# -----------------------------------------------------------------------------
# Aggregators (optional deep-links for Delivery Options UI)
# -----------------------------------------------------------------------------
UBEREATS_ORDER_URL = os.getenv("UBEREATS_ORDER_URL", "")
DOORDASH_ORDER_URL = os.getenv("DOORDASH_ORDER_URL", "")

# -----------------------------------------------------------------------------
# Third-party Delivery APIs
# -----------------------------------------------------------------------------
# DoorDash API
DOORDASH_API_KEY = os.getenv("DOORDASH_API_KEY", "")
DOORDASH_API_SECRET = os.getenv("DOORDASH_API_SECRET", "")
DOORDASH_ENVIRONMENT = os.getenv("DOORDASH_ENVIRONMENT", "sandbox")

# Uber Eats API
UBEREATS_CLIENT_ID = os.getenv("UBEREATS_CLIENT_ID", "")
UBEREATS_CLIENT_SECRET = os.getenv("UBEREATS_CLIENT_SECRET", "")
UBEREATS_ACCESS_TOKEN = os.getenv("UBEREATS_ACCESS_TOKEN", "")
UBEREATS_ENVIRONMENT = os.getenv("UBEREATS_ENVIRONMENT", "sandbox")

# -----------------------------------------------------------------------------
# Celery
# -----------------------------------------------------------------------------
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE  # <-- fixed (no trailing dot)

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "file": {
            "level": "INFO",
            "class": "logging.FileHandler",
            "filename": BASE_DIR / "logs" / "django.log",
            "formatter": "verbose",
        },
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING" if not DEBUG else "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file"] if not DEBUG else ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console", "file"] if not DEBUG else ["console"],
            "level": "ERROR",
            "propagate": False,
        },
        "payments": {
            "handlers": ["console", "file"] if not DEBUG else ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
