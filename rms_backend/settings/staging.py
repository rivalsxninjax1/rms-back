# rms_backend/settings/staging.py
from .production import *

# -----------------------------------------------------------------------------
# Staging Settings (Production-like with debugging capabilities)
# -----------------------------------------------------------------------------

# Allow some debugging in staging
DEBUG = os.getenv("DEBUG", "0") == "1"

# Less strict host validation for staging
ALLOWED_HOSTS = _split_csv("DJANGO_ALLOWED_HOSTS") or ["*"]

# -----------------------------------------------------------------------------
# Security Settings (Relaxed for Staging)
# -----------------------------------------------------------------------------
# Optional HTTPS for staging
SECURE_SSL_REDIRECT = os.getenv("FORCE_HTTPS", "0") == "1"
SESSION_COOKIE_SECURE = SECURE_SSL_REDIRECT
CSRF_COOKIE_SECURE = SECURE_SSL_REDIRECT

# Reduced HSTS for staging
SECURE_HSTS_SECONDS = 3600  # 1 hour
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False

# -----------------------------------------------------------------------------
# Database Configuration (Staging)
# -----------------------------------------------------------------------------
# Allow fallback to SQLite for staging
if not os.getenv("DATABASE_URL") and not os.getenv("PG_NAME"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db_staging.sqlite3",
            "OPTIONS": {
                "timeout": 20,
            },
        }
    }
    import warnings
    warnings.warn("Using SQLite in staging - not recommended for production testing")

# -----------------------------------------------------------------------------
# Email Configuration (Staging)
# -----------------------------------------------------------------------------
# Use console backend if no email config
if not EMAIL_HOST:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
    import warnings
    warnings.warn("Using console email backend in staging")

# -----------------------------------------------------------------------------
# Logging Configuration (Staging)
# -----------------------------------------------------------------------------
# More verbose logging for staging
LOGGING["root"]["level"] = "INFO"
LOGGING["loggers"]["django"]["level"] = "INFO"

# Add debug logging for specific apps
LOGGING["loggers"]["orders"]["level"] = "DEBUG"
LOGGING["loggers"]["payments"]["level"] = "DEBUG"
LOGGING["loggers"]["accounts"]["level"] = "DEBUG"

# Enable SQL logging if requested
if os.getenv("LOG_SQL", "0") == "1":
    LOGGING["loggers"]["django.db.backends"] = {
        "handlers": ["console", "file"],
        "level": "DEBUG",
        "propagate": False,
    }

# -----------------------------------------------------------------------------
# API Configuration (Staging)
# -----------------------------------------------------------------------------
# Allow browsable API in staging
REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = [
    "rest_framework.renderers.JSONRenderer",
    "rest_framework.renderers.BrowsableAPIRenderer",
]

# More permissive throttle rates for testing
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
    "anon": "1000/hour",
    "user": "5000/hour",
    "login": "20/min",
    "register": "10/min",
}

# -----------------------------------------------------------------------------
# CORS Configuration (Staging)
# -----------------------------------------------------------------------------
# More permissive CORS for staging
if not CORS_ALLOWED_ORIGINS:
    CORS_ALLOW_ALL_ORIGINS = True
    import warnings
    warnings.warn("CORS_ALLOW_ALL_ORIGINS is True in staging")

# -----------------------------------------------------------------------------
# Debug Toolbar (Staging)
# -----------------------------------------------------------------------------
if DEBUG and os.getenv("ENABLE_DEBUG_TOOLBAR", "0") == "1":
    try:
        import debug_toolbar
        INSTALLED_APPS.append("debug_toolbar")
        MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")
        
        # Debug toolbar settings
        DEBUG_TOOLBAR_CONFIG = {
            "SHOW_TOOLBAR_CALLBACK": lambda request: True,
            "SHOW_COLLAPSED": True,
        }
        
        INTERNAL_IPS = ["127.0.0.1", "localhost"]
        
    except ImportError:
        import warnings
        warnings.warn("debug_toolbar not installed")

# -----------------------------------------------------------------------------
# Testing Configuration
# -----------------------------------------------------------------------------
# Enable test database creation
if "test" in sys.argv:
    DATABASES["default"] = {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
    
    # Disable migrations for faster tests
    class DisableMigrations:
        def __contains__(self, item):
            return True
        
        def __getitem__(self, item):
            return None
    
    MIGRATION_MODULES = DisableMigrations()
    
    # Use dummy cache for tests
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.dummy.DummyCache",
        }
    }
    
    # Disable Celery for tests
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True

# -----------------------------------------------------------------------------
# File Upload (Staging)
# -----------------------------------------------------------------------------
# More permissive file upload for testing
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB

# -----------------------------------------------------------------------------
# Error Monitoring (Staging)
# -----------------------------------------------------------------------------
# Optional Sentry for staging
if not SENTRY_DSN:
    import warnings
    warnings.warn("Sentry not configured for staging")

# -----------------------------------------------------------------------------
# Performance Monitoring (Staging)
# -----------------------------------------------------------------------------
# Enable performance monitoring
if os.getenv("ENABLE_SILK", "0") == "1":
    try:
        import silk
        INSTALLED_APPS.append("silk")
        MIDDLEWARE.append("silk.middleware.SilkyMiddleware")
        
        # Silk settings
        SILKY_PYTHON_PROFILER = True
        SILKY_PYTHON_PROFILER_BINARY = True
        SILKY_AUTHENTICATION = True
        SILKY_AUTHORISATION = True
        
    except ImportError:
        import warnings
        warnings.warn("django-silk not installed")

# -----------------------------------------------------------------------------
# Cache Configuration (Staging)
# -----------------------------------------------------------------------------
# Allow fallback to local memory cache
if not os.getenv("REDIS_URL"):
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "staging-cache",
            "OPTIONS": {
                "MAX_ENTRIES": 1000,
            },
        }
    }
    import warnings
    warnings.warn("Using local memory cache in staging")

# -----------------------------------------------------------------------------
# Session Configuration (Staging)
# -----------------------------------------------------------------------------
# Use database sessions if no cache
if CACHES["default"]["BACKEND"] == "django.core.cache.backends.locmem.LocMemCache":
    SESSION_ENGINE = "django.contrib.sessions.backends.db"

print("\n" + "="*50)
print("STAGING SETTINGS LOADED")
print(f"DEBUG: {DEBUG}")
print(f"ALLOWED_HOSTS: {ALLOWED_HOSTS}")
print(f"DATABASE: {DATABASES['default']['ENGINE']}")
print(f"CACHE: {CACHES['default']['BACKEND']}")
print(f"EMAIL: {EMAIL_BACKEND}")
print(f"SENTRY: {'Enabled' if SENTRY_DSN else 'Disabled'}")
print("="*50 + "\n")