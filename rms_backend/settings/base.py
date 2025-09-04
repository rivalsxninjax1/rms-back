# rms_backend/settings/base.py
from __future__ import annotations

import os
from pathlib import Path
from datetime import timedelta
from urllib.parse import urlparse

from dotenv import load_dotenv

# -----------------------------------------------------------------------------
# Paths / env
# -----------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")

# Public site/base URL used for building absolute redirect URLs (Stripe requires absolute)
# Example: http://localhost:8000 or https://yourdomain.com
SITE_URL = os.getenv("SITE_URL", "http://localhost:8000").rstrip("/")

# -----------------------------------------------------------------------------
# Core Security Settings
# -----------------------------------------------------------------------------
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("DJANGO_SECRET_KEY environment variable is required")

DEBUG = False  # Default to False, override in development

def _split_csv(name: str, default: str = "") -> list[str]:
    raw = os.getenv(name, default) or ""
    return [s.strip() for s in raw.split(",") if s.strip()]

ALLOWED_HOSTS = _split_csv("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost")

# Trust same as ALLOWED_HOSTS plus scheme-explicit origins if provided
CSRF_TRUSTED_ORIGINS = _split_csv(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    ",".join([f"http://{h}" for h in ALLOWED_HOSTS] + [f"https://{h}" for h in ALLOWED_HOSTS]),
)

# -----------------------------------------------------------------------------
# Applications
# -----------------------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt",
    "django_filters",
    "drf_spectacular",
    "channels",
]

LOCAL_APPS = [
    "accounts",
    "core",
    "menu",
    "inventory",
    "orders",
    "orders_extras",
    "coupons",
    "payments",
    "reservations",
    "loyalty.apps.LoyaltyConfig",
    "billing",
    "reports",
    "engagement",
    "storefront",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# Keep migrations under the legacy module path for the historical app label
MIGRATION_MODULES = globals().get("MIGRATION_MODULES", {}) or {}
MIGRATION_MODULES.update({
    # Point the historical app label to the canonical loyalty package migrations
    "loyality": "loyalty.migrations",
})

# -----------------------------------------------------------------------------
# Middleware
# -----------------------------------------------------------------------------
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "core.middleware.request_id.RequestIDMiddleware",
    "core.rate_limiting.SecurityHeadersMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "core.middleware.cache_middleware.CachePerformanceMiddleware",

    "core.rate_limiting.RateLimitMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "orders.middleware.EnsureCartInitializedMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "reports.middleware.AuditLogMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.cache_middleware.CacheInvalidationMiddleware",
    "core.middleware.cache_middleware.CacheCompressionMiddleware",
]

ROOT_URLCONF = "rms_backend.urls"

# -----------------------------------------------------------------------------
# Templates
# -----------------------------------------------------------------------------
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            BASE_DIR / "templates",
            BASE_DIR / "frontend" / "rms_admin_spa",  # so index.html is found
        ],
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
ASGI_APPLICATION = "rms_backend.asgi.application"
# Channels layer: prefer Redis if REDIS_URL set; fallback to in-memory (dev/tests)
REDIS_URL = os.getenv("REDIS_URL", "").strip()
if REDIS_URL:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [REDIS_URL]},
        }
    }
else:
    CHANNEL_LAYERS = {
        "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}
    }

# -----------------------------------------------------------------------------
# Database Configuration
# -----------------------------------------------------------------------------
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
                "OPTIONS": {
                    "sslmode": "require" if os.getenv("DB_SSL_REQUIRE", "0") == "1" else "prefer",
                },
                "CONN_MAX_AGE": int(os.getenv("DB_CONN_MAX_AGE", "60")),
            }
        }
    else:
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
                "OPTIONS": {
                    "sslmode": "require" if os.getenv("DB_SSL_REQUIRE", "0") == "1" else "prefer",
                },
                "CONN_MAX_AGE": int(os.getenv("DB_CONN_MAX_AGE", "60")),
            }
        }
    else:
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": BASE_DIR / "db.sqlite3",
            }
        }

# Database connection pooling
DATABASE_POOL_URL = os.getenv("DATABASE_POOL_URL")
if DATABASE_POOL_URL:
    DATABASES["default"]["ENGINE"] = "django_db_geventpool.backends.postgresql_psycopg2"
    DATABASES["default"]["OPTIONS"]["MAX_CONNS"] = int(os.getenv("DB_POOL_MAX_CONNS", "20"))

# -----------------------------------------------------------------------------
# Authentication & Authorization
# -----------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
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
# Static & Media Files
# -----------------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [
    BASE_DIR / "static",
    BASE_DIR / "frontend" / "rms_admin_spa",  # where React build is copied
]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# File upload settings
FILE_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv("FILE_UPLOAD_MAX_MEMORY_SIZE", "2621440"))  # 2.5MB
DATA_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv("DATA_UPLOAD_MAX_MEMORY_SIZE", "2621440"))  # 2.5MB
FILE_UPLOAD_PERMISSIONS = 0o644
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o755

# Storage configuration
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {
            "location": str(MEDIA_ROOT),
            "base_url": MEDIA_URL,
        },
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# -----------------------------------------------------------------------------
# Django REST Framework
# -----------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": int(os.getenv("DRF_PAGE_SIZE", "20")),
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": os.getenv("DRF_ANON_THROTTLE_RATE", "100/hour"),
        "user": os.getenv("DRF_USER_THROTTLE_RATE", "1000/hour"),
    },
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.FormParser",
        "rest_framework.parsers.MultiPartParser",
    ],
}

# -----------------------------------------------------------------------------
# Reservation Configuration (env-driven)
# -----------------------------------------------------------------------------
# Max simultaneous overlapping reservations a user can hold
RESERVATION_MAX_TABLES = int(os.getenv("RESERVATION_MAX_TABLES", "1") or 1)
# Minutes after start to mark as no-show/cancel if not checked in
RESERVATION_AUTO_CANCEL_MINUTES = int(os.getenv("RESERVATION_AUTO_CANCEL_MINUTES", "20") or 20)
# Deposit configuration
# 1) Flat total deposit per reservation (takes precedence when > 0)
RESERVATION_DEPOSIT_FLAT_TOTAL = os.getenv("RESERVATION_DEPOSIT_FLAT_TOTAL", "0").strip()
try:
    RESERVATION_DEPOSIT_FLAT_TOTAL = float(RESERVATION_DEPOSIT_FLAT_TOTAL or 0)
except Exception:
    RESERVATION_DEPOSIT_FLAT_TOTAL = 0.0
# 2) Per-seat deposit (used only if flat total is 0)
RESERVATION_DEPOSIT_PER_SEAT = os.getenv("RESERVATION_DEPOSIT_PER_SEAT", "0").strip()
try:
    RESERVATION_DEPOSIT_PER_SEAT = float(RESERVATION_DEPOSIT_PER_SEAT or 0)
except Exception:
    RESERVATION_DEPOSIT_PER_SEAT = 0.0
# Max no-shows before action
RESERVATION_MAX_NO_SHOWS = int(os.getenv("RESERVATION_MAX_NO_SHOWS", "3") or 3)
# Action when limit reached: 'block' or 'require_prepayment'
RESERVATION_NO_SHOW_ACTION = (os.getenv("RESERVATION_NO_SHOW_ACTION", "require_prepayment") or "require_prepayment").lower()

# API Documentation
SPECTACULAR_SETTINGS = {
    "TITLE": "RMS API (Unified Models)",
    "DESCRIPTION": (
        "Restaurant Management System API.\n\n"
        "This revision unifies duplicate models and standardizes cart/order endpoints.\n"
        "Legacy loyalty endpoints remain available under /api/loyality/ but are deprecated."
    ),
    "VERSION": "2.0.0",
    # Generate only for API routes
    "SCHEMA_PATH_PREFIX": r"/api",
    # Serve the generated schema & docs endpoints
    "SERVE_INCLUDE_SCHEMA": True,
    "SERVE_PUBLIC": True,
    # Component behavior
    "COMPONENT_SPLIT_REQUEST": True,
    "SORT_OPERATIONS": False,
    # Security: both session and bearer JWT are supported
    "SECURITY": [
        {"BearerAuth": []},
        {"SessionAuth": []},
    ],
    # Add/override components (security schemes)
    "APPEND_COMPONENTS": {
        "securitySchemes": {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "JWT Authorization header using the Bearer scheme. Example: 'Authorization: Bearer <token>'",
            },
            "SessionAuth": {
                "type": "apiKey",
                "in": "cookie",
                "name": globals().get("SESSION_COOKIE_NAME", "rms_sessionid"),
                "description": "Session cookie authentication. Include CSRF header 'X-CSRFToken' for unsafe methods.",
            },
        }
    },
    # Post-processing hook to mark deprecated paths & add metadata
    "POSTPROCESSING_HOOKS": [
        "core.openapi_hooks.deprecate_paths_hook",
    ],
    # Swagger UI tweaks (when using spectacular views)
    "SWAGGER_UI_SETTINGS": {
        "deepLinking": True,
        "displayRequestDuration": True,
        "tryItOutEnabled": True,
    },
}

# -----------------------------------------------------------------------------
# JWT Configuration
# -----------------------------------------------------------------------------
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(os.getenv("JWT_ACCESS_MINUTES", "15"))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(os.getenv("JWT_REFRESH_DAYS", "7"))),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "VERIFYING_KEY": None,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "TOKEN_TYPE_CLAIM": "token_type",
}

# -----------------------------------------------------------------------------
# Session Configuration
# -----------------------------------------------------------------------------
SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"
SESSION_COOKIE_AGE = int(os.getenv("SESSION_COOKIE_AGE", str(60 * 60 * 24 * 7)))  # 7 days
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_COOKIE_NAME = "rms_sessionid"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = True  # Override in development

# -----------------------------------------------------------------------------
# Security Settings
# -----------------------------------------------------------------------------
# CSRF Protection
CSRF_COOKIE_SECURE = True  # Override in development
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_USE_SESSIONS = False
CSRF_COOKIE_AGE = 31449600  # 1 year

# HTTPS Security
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "31536000"))  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_SSL_REDIRECT = True  # Override in development
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Content Security
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

# -----------------------------------------------------------------------------
# CORS Configuration
# -----------------------------------------------------------------------------
CORS_ALLOW_ALL_ORIGINS = False  # Never allow all origins in production
CORS_ALLOWED_ORIGINS = _split_csv("CORS_ALLOWED_ORIGINS", "")
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
]

# -----------------------------------------------------------------------------
# Rate Limiting Configuration
# -----------------------------------------------------------------------------
RATE_LIMIT_DEFAULTS = {
    'anonymous': int(os.getenv('RATE_LIMIT_ANONYMOUS', '300')),  # requests per minute (increased from 60)
    'authenticated': int(os.getenv('RATE_LIMIT_AUTHENTICATED', '1000')),  # requests per minute (increased from 300)
    'burst': int(os.getenv('RATE_LIMIT_BURST', '50')),  # requests per 10 seconds (increased from 10)
}

RATE_LIMIT_ENDPOINTS = {
    '/api/auth/login/': {
        'anonymous': int(os.getenv('RATE_LIMIT_LOGIN_ANON', '20')),  # increased from 5
        'authenticated': int(os.getenv('RATE_LIMIT_LOGIN_AUTH', '50'))  # increased from 10
    },
    '/api/auth/register/': {
        'anonymous': int(os.getenv('RATE_LIMIT_REGISTER_ANON', '15')),  # increased from 3
        'authenticated': int(os.getenv('RATE_LIMIT_REGISTER_AUTH', '25'))  # increased from 5
    },
    '/api/auth/password-reset/': {
        'anonymous': int(os.getenv('RATE_LIMIT_PASSWORD_RESET_ANON', '10')),  # increased from 2
        'authenticated': int(os.getenv('RATE_LIMIT_PASSWORD_RESET_AUTH', '15'))  # increased from 3
    },
    '/api/orders/': {
        'anonymous': int(os.getenv('RATE_LIMIT_ORDERS_ANON', '100')),  # increased from 20
        'authenticated': int(os.getenv('RATE_LIMIT_ORDERS_AUTH', '500'))  # increased from 100
    },
    '/api/reservations/': {
        'anonymous': int(os.getenv('RATE_LIMIT_RESERVATIONS_ANON', '50')),  # increased from 10
        'authenticated': int(os.getenv('RATE_LIMIT_RESERVATIONS_AUTH', '200'))  # increased from 50
    },
}

RATE_LIMIT_WHITELIST = _split_csv('RATE_LIMIT_WHITELIST', '')
RATE_LIMIT_BLACKLIST = _split_csv('RATE_LIMIT_BLACKLIST', '')

# -----------------------------------------------------------------------------
# Third-party Service Configuration
# -----------------------------------------------------------------------------
# Stripe
STRIPE_PUBLIC_KEY = os.getenv("STRIPE_PUBLIC_KEY", "")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_CURRENCY = (os.getenv("STRIPE_CURRENCY", "usd") or "usd").lower()

# External APIs
UBEREATS_ORDER_URL = os.getenv("UBEREATS_ORDER_URL", "")
DOORDASH_ORDER_URL = os.getenv("DOORDASH_ORDER_URL", "")
DOORDASH_API_KEY = os.getenv("DOORDASH_API_KEY", "")
DOORDASH_API_SECRET = os.getenv("DOORDASH_API_SECRET", "")
DOORDASH_ENVIRONMENT = os.getenv("DOORDASH_ENVIRONMENT", "sandbox")
UBEREATS_CLIENT_ID = os.getenv("UBEREATS_CLIENT_ID", "")
UBEREATS_CLIENT_SECRET = os.getenv("UBEREATS_CLIENT_SECRET", "")
UBEREATS_ACCESS_TOKEN = os.getenv("UBEREATS_ACCESS_TOKEN", "")
UBEREATS_ENVIRONMENT = os.getenv("UBEREATS_ENVIRONMENT", "sandbox")

# Optional platform fees (absolute amounts added to service fees)
UBEREATS_FEE = float(os.getenv("UBEREATS_FEE", "0"))
DOORDASH_FEE = float(os.getenv("DOORDASH_FEE", "0"))

# Table reservation duration (minutes) after successful dine-in payment
TABLE_RESERVE_MINUTES = int(os.getenv("TABLE_RESERVE_MINUTES", "30"))

# -----------------------------------------------------------------------------
# Printing / Ticketing
# -----------------------------------------------------------------------------
# Enable writing kitchen ticket PDFs to MEDIA_ROOT/tickets when orders are paid
PRINT_TICKETS = int(os.getenv("PRINT_TICKETS", "0") or 0)
# Optional: printer name/queue identifier if/when direct printing is implemented
PRINTER_NAME = os.getenv("PRINTER_NAME", "")

# -----------------------------------------------------------------------------
# Celery Configuration
# -----------------------------------------------------------------------------
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_ENABLE_UTC = True
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = int(os.getenv("CELERY_TASK_TIME_LIMIT", "300"))  # 5 minutes
CELERY_WORKER_PREFETCH_MULTIPLIER = int(os.getenv("CELERY_WORKER_PREFETCH_MULTIPLIER", "1"))

# Celery Task Routing and Queues
CELERY_TASK_ROUTES = {
    # Post-payment processing tasks
    'payments.tasks.run_post_payment_hooks_task': {'queue': 'post_payment'},
    'payments.tasks.send_order_confirmation_email_task': {'queue': 'emails'},
    'payments.tasks.send_staff_notification_task': {'queue': 'emails'},
    'payments.tasks.sync_order_to_pos_task': {'queue': 'pos_sync'},
    'payments.tasks.record_payment_analytics_task': {'queue': 'analytics'},
    'payments.tasks.process_loyalty_rewards_task': {'queue': 'loyalty'},
    'payments.tasks.update_inventory_levels_task': {'queue': 'inventory'},
    # Default queue for other tasks
    '*': {'queue': 'default'},
}

CELERY_TASK_DEFAULT_QUEUE = 'default'
CELERY_TASK_CREATE_MISSING_QUEUES = True

# Task priorities and retry policies
CELERY_TASK_ANNOTATIONS = {
    'payments.tasks.send_order_confirmation_email_task': {
        'rate_limit': '10/m',
        'max_retries': 3,
        'default_retry_delay': 60,
    },
    'payments.tasks.send_staff_notification_task': {
        'rate_limit': '20/m',
        'max_retries': 3,
        'default_retry_delay': 30,
    },
    'payments.tasks.sync_order_to_pos_task': {
        'rate_limit': '5/m',
        'max_retries': 5,
        'default_retry_delay': 120,
    },
    'payments.tasks.record_payment_analytics_task': {
        'rate_limit': '50/m',
        'max_retries': 2,
        'default_retry_delay': 30,
    },
    'payments.tasks.process_loyalty_rewards_task': {
        'rate_limit': '15/m',
        'max_retries': 3,
        'default_retry_delay': 60,
    },
    'payments.tasks.update_inventory_levels_task': {
        'rate_limit': '30/m',
        'max_retries': 3,
        'default_retry_delay': 45,
    },
}

# Optional periodic tasks
CELERY_BEAT_SCHEDULE = {
    'auto_cancel_no_shows': {
        'task': 'reservations.tasks_portal.auto_cancel_no_show_reservations',
        'schedule': int(os.getenv('RESERVATION_AUTOCANCEL_CHECK_SECONDS', '60') or 60),
    },
}

# -----------------------------------------------------------------------------
# Caching Configuration
# -----------------------------------------------------------------------------
REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/1")

# Import cache configuration
from core.cache_config import get_cache_config, CACHE_TIMEOUTS

# Flag to disable caching system entirely
CACHE_DISABLED = os.getenv("CACHE_DISABLED", "0") == "1"

# Use environment-specific cache configuration (unless disabled)
if CACHE_DISABLED:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
        }
    }
else:
    CACHES = get_cache_config()

# Override with Redis if available in production
if not DEBUG and REDIS_URL and not CACHE_DISABLED:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                "PARSER_CLASS": "redis.connection.HiredisParser",
                "CONNECTION_POOL_KWARGS": {
                    "max_connections": int(os.getenv("REDIS_MAX_CONNECTIONS", "50")),
                    "retry_on_timeout": True,
                },
                "COMPRESSOR": "django_redis.compressors.zlib.ZlibCompressor",
                "SERIALIZER": "django_redis.serializers.json.JSONSerializer",
            },
            "KEY_PREFIX": "rms",
            "VERSION": 1,
            "TIMEOUT": CACHE_TIMEOUTS['DEFAULT'],
        }
    }

# Cache middleware settings
CACHE_MIDDLEWARE_ALIAS = "default"
CACHE_MIDDLEWARE_SECONDS = int(os.getenv("CACHE_MIDDLEWARE_SECONDS", "600"))  # 10 minutes
CACHE_MIDDLEWARE_KEY_PREFIX = "rms"

# Cache configuration settings
CACHE_WARMUP_ENABLED = os.getenv("CACHE_WARMUP_ENABLED", "1") == "1"
CACHE_WARMUP_ON_STARTUP = os.getenv("CACHE_WARMUP_ON_STARTUP", "0") == "1"
CACHE_MONITORING_ENABLED = os.getenv("CACHE_MONITORING_ENABLED", str(DEBUG).lower()) == "true"
CACHE_KEY_PREFIX = os.getenv("CACHE_KEY_PREFIX", "rms")
CACHE_VERSION = int(os.getenv("CACHE_VERSION", "1"))

# -----------------------------------------------------------------------------
# Logging Configuration
# -----------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {request_id} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(name)s %(levelname)s %(request_id)s %(message)s %(pathname)s %(lineno)d",
        },
    },
    "filters": {
        "require_debug_false": {
            "()": "django.utils.log.RequireDebugFalse",
        },
        "require_debug_true": {
            "()": "django.utils.log.RequireDebugTrue",
        },
        "request_id": {
            "()": "core.middleware.request_id.RequestIDFilter",
        },
    },
    "handlers": {
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "simple",
            "filters": ["request_id"],
        },
        "file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": BASE_DIR / "logs" / "django.log",
            "maxBytes": 1024 * 1024 * 15,  # 15MB
            "backupCount": 10,
            "formatter": "verbose",
            "filters": ["request_id"],
        },
        "error_file": {
            "level": "ERROR",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": BASE_DIR / "logs" / "django_errors.log",
            "maxBytes": 1024 * 1024 * 15,  # 15MB
            "backupCount": 10,
            "formatter": "verbose",
            "filters": ["request_id"],
        },
        "security_file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": BASE_DIR / "logs" / "security.log",
            "maxBytes": 1024 * 1024 * 15,  # 15MB
            "backupCount": 10,
            "formatter": "verbose",
            "filters": ["request_id"],
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console", "error_file"],
            "level": "ERROR",
            "propagate": False,
        },
        "django.security": {
            "handlers": ["security_file"],
            "level": "INFO",
            "propagate": False,
        },
        "payments": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "orders": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "accounts": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "core.cache_service": {
            "handlers": ["console", "file"],
            "level": "DEBUG" if DEBUG else "INFO",
            "propagate": False,
        },
        "core.middleware.cache_middleware": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# -----------------------------------------------------------------------------
# Application-specific Settings
# -----------------------------------------------------------------------------
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/admin/"
LOGOUT_REDIRECT_URL = "/"

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Email configuration
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "1") == "1"
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "noreply@example.com")
SERVER_EMAIL = os.getenv("SERVER_EMAIL", DEFAULT_FROM_EMAIL)

# Admin configuration
ADMINS = [("Admin", os.getenv("ADMIN_EMAIL", "admin@example.com"))]
MANAGERS = ADMINS
