# rms_backend/settings/development.py
from .base import *

# -----------------------------------------------------------------------------
# Development Settings
# -----------------------------------------------------------------------------
DEBUG = True

# Allow all hosts in development
ALLOWED_HOSTS = ["*"]

# CORS - Allow all origins in development
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOWED_ORIGINS = []

# CSRF - Add frontend URL to trusted origins
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

# -----------------------------------------------------------------------------
# Security Settings (Relaxed for Development)
# -----------------------------------------------------------------------------
# Disable HTTPS requirements in development
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False

# Allow embedding in frames for development
X_FRAME_OPTIONS = "SAMEORIGIN"

# -----------------------------------------------------------------------------
# Database Configuration
# -----------------------------------------------------------------------------
# Use SQLite for development if no DATABASE_URL is provided
if not os.getenv("DATABASE_URL") and not os.getenv("PG_NAME"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# -----------------------------------------------------------------------------
# Email Configuration (Development)
# -----------------------------------------------------------------------------
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# -----------------------------------------------------------------------------
# Logging Configuration (Development)
# -----------------------------------------------------------------------------
LOGGING["root"]["level"] = "INFO"
LOGGING["loggers"]["django"]["level"] = "DEBUG"
LOGGING["loggers"]["django"]["handlers"] = ["console"]
LOGGING["loggers"]["django.request"]["handlers"] = ["console"]
LOGGING["loggers"]["payments"]["handlers"] = ["console"]
LOGGING["loggers"]["orders"]["handlers"] = ["console"]
LOGGING["loggers"]["accounts"]["handlers"] = ["console"]
LOGGING["loggers"]["core.cache_service"]["handlers"] = ["console"]
LOGGING["loggers"]["core.middleware.cache_middleware"]["handlers"] = ["console"]

# Add development-specific loggers
LOGGING["loggers"]["django.db.backends"] = {
    "handlers": ["console"],
    "level": "DEBUG" if os.getenv("DEBUG_SQL", "0") == "1" else "INFO",
    "propagate": False,
}

# -----------------------------------------------------------------------------
# Cache Configuration (Development)
# -----------------------------------------------------------------------------
# Disable caching entirely in development to avoid cache-related noise
CACHE_DISABLED = True
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
    }
}

# Disable cache warmup/monitoring
CACHE_MONITORING_ENABLED = False
CACHE_WARMUP_ENABLED = False
CACHE_WARMUP_ON_STARTUP = False

# No tax and platform fees in development
DEFAULT_TAX_RATE = '0.00'
UBEREATS_FEE = '0.00'
DOORDASH_FEE = '0.00'

# -----------------------------------------------------------------------------
# Static Files (Development)
# -----------------------------------------------------------------------------
# Include our static directory for development
STATICFILES_DIRS = [BASE_DIR / "static"]

# Use regular static files storage in development
STORAGES["staticfiles"] = {
    "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
}

# -----------------------------------------------------------------------------
# Django Extensions (Development)
# -----------------------------------------------------------------------------
if "django_extensions" not in INSTALLED_APPS:
    INSTALLED_APPS.append("django_extensions")

# -----------------------------------------------------------------------------
# Debug Toolbar (Development)
# -----------------------------------------------------------------------------
if os.getenv("USE_DEBUG_TOOLBAR", "0") == "1":
    INSTALLED_APPS.append("debug_toolbar")
    MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")
    
    DEBUG_TOOLBAR_CONFIG = {
        "SHOW_TOOLBAR_CALLBACK": lambda request: DEBUG,
        "SHOW_COLLAPSED": True,
    }
    
    INTERNAL_IPS = [
        "127.0.0.1",
        "localhost",
    ]

# Remove cache-related middlewares when cache is disabled
if CACHE_DISABLED:
    MIDDLEWARE = [
        mw for mw in MIDDLEWARE
        if not mw.startswith("core.middleware.cache_middleware.")
    ]


# -----------------------------------------------------------------------------
# DRF Configuration (Development)
# -----------------------------------------------------------------------------
# Add browsable API renderer for development
REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = [
    "rest_framework.renderers.JSONRenderer",
    "rest_framework.renderers.BrowsableAPIRenderer",
]

# More permissive permissions for development
REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"] = [
    "rest_framework.permissions.AllowAny",
]

# Higher throttle rates for development
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
    "anon": "1000/hour",
    "user": "10000/hour",
    "login": "100/min",
    "register": "50/min",
    "password_reset": "20/min",
}

# -----------------------------------------------------------------------------
# JWT Configuration (Development)
# -----------------------------------------------------------------------------
# Longer token lifetime for development convenience
SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"] = timedelta(hours=1)
SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"] = timedelta(days=30)

# -----------------------------------------------------------------------------
# Session Configuration (Development)
# -----------------------------------------------------------------------------
# Use the same session engine as base settings for consistency
# SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"  # Inherited from base

# -----------------------------------------------------------------------------
# File Upload Settings (Development)
# -----------------------------------------------------------------------------
# More generous file upload limits for development
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB

# -----------------------------------------------------------------------------
# Development-specific Settings
# -----------------------------------------------------------------------------
# Show detailed error pages
DEBUG_PROPAGATE_EXCEPTIONS = True

# Disable template caching
for template_engine in TEMPLATES:
    template_engine["OPTIONS"]["debug"] = True
    if "loaders" in template_engine["OPTIONS"]:
        template_engine["OPTIONS"]["loaders"] = [
            "django.template.loaders.filesystem.Loader",
            "django.template.loaders.app_directories.Loader",
        ]

# Print emails to console
print("\n" + "="*50)
print("DEVELOPMENT SETTINGS LOADED")
print(f"DEBUG: {DEBUG}")
print(f"DATABASE: {DATABASES['default']['ENGINE']}")
print(f"CACHE: {CACHES['default']['BACKEND']}")
print(f"EMAIL: {EMAIL_BACKEND}")
print("="*50 + "\n")
