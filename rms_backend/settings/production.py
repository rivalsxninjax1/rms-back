# rms_backend/settings/production.py
from .base import *
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.redis import RedisIntegration

# -----------------------------------------------------------------------------
# Production Settings
# -----------------------------------------------------------------------------
DEBUG = False

# Strict host validation
ALLOWED_HOSTS = _split_csv("DJANGO_ALLOWED_HOSTS")
if not ALLOWED_HOSTS:
    raise ValueError("DJANGO_ALLOWED_HOSTS must be set in production")

# -----------------------------------------------------------------------------
# Security Settings (Enhanced for Production)
# -----------------------------------------------------------------------------
# Force HTTPS
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# HSTS Settings
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Additional security headers
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

# Content Security Policy
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'", "'unsafe-inline'", "https://js.stripe.com")
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'")
CSP_IMG_SRC = ("'self'", "data:", "https:")
CSP_FONT_SRC = ("'self'", "https:")
CSP_CONNECT_SRC = ("'self'", "https://api.stripe.com")
CSP_FRAME_SRC = ("https://js.stripe.com", "https://hooks.stripe.com")

# -----------------------------------------------------------------------------
# Database Configuration (Production)
# -----------------------------------------------------------------------------
# Ensure database connection is configured
if not os.getenv("DATABASE_URL") and not os.getenv("PG_NAME"):
    raise ValueError("Database configuration is required in production")

# Enable connection pooling
DATABASES["default"]["CONN_MAX_AGE"] = 600  # 10 minutes
DATABASES["default"]["OPTIONS"] = {
    "sslmode": "require",
    "options": "-c default_transaction_isolation=read_committed"
}

# -----------------------------------------------------------------------------
# Cache Configuration (Production)
# -----------------------------------------------------------------------------
# Ensure Redis is configured
if not os.getenv("REDIS_URL"):
    raise ValueError("REDIS_URL must be set in production")

# Add cache middleware only if cache is enabled
if not CACHE_DISABLED:
    MIDDLEWARE.insert(1, "django.middleware.cache.UpdateCacheMiddleware")
    MIDDLEWARE.append("django.middleware.cache.FetchFromCacheMiddleware")

# -----------------------------------------------------------------------------
# Session Configuration (Production)
# -----------------------------------------------------------------------------
SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"
SESSION_CACHE_ALIAS = "default"

# -----------------------------------------------------------------------------
# Static Files (Production)
# -----------------------------------------------------------------------------
# Use WhiteNoise with compression
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
WHITENOISE_USE_FINDERS = True
WHITENOISE_AUTOREFRESH = False

# -----------------------------------------------------------------------------
# Media Files (Production)
# -----------------------------------------------------------------------------
# Configure for cloud storage if needed
if os.getenv("USE_S3_STORAGE", "0") == "1":
    # AWS S3 Configuration
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
    AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME")
    AWS_S3_REGION_NAME = os.getenv("AWS_S3_REGION_NAME", "us-east-1")
    AWS_S3_CUSTOM_DOMAIN = os.getenv("AWS_S3_CUSTOM_DOMAIN")
    AWS_DEFAULT_ACL = "public-read"
    AWS_S3_OBJECT_PARAMETERS = {
        "CacheControl": "max-age=86400",
    }
    AWS_S3_FILE_OVERWRITE = False
    AWS_QUERYSTRING_AUTH = False
    
    # Update storage backends
    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        "OPTIONS": {
            "bucket_name": AWS_STORAGE_BUCKET_NAME,
            "region_name": AWS_S3_REGION_NAME,
            "custom_domain": AWS_S3_CUSTOM_DOMAIN,
            "default_acl": AWS_DEFAULT_ACL,
            "file_overwrite": AWS_S3_FILE_OVERWRITE,
            "querystring_auth": AWS_QUERYSTRING_AUTH,
        },
    }
    
    MEDIA_URL = f"https://{AWS_S3_CUSTOM_DOMAIN or f'{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com'}/"

# -----------------------------------------------------------------------------
# Email Configuration (Production)
# -----------------------------------------------------------------------------
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

# Ensure email configuration is set
if not EMAIL_HOST:
    raise ValueError("Email configuration is required in production")

# -----------------------------------------------------------------------------
# Logging Configuration (Production)
# -----------------------------------------------------------------------------
# Enhanced logging for production
LOGGING["handlers"]["syslog"] = {
    "level": "INFO",
    "class": "logging.handlers.SysLogHandler",
    "formatter": "verbose",
    "address": "/dev/log" if os.path.exists("/dev/log") else ("localhost", 514),
}

# Add structured logging
if os.getenv("USE_JSON_LOGGING", "0") == "1":
    LOGGING["handlers"]["json_file"] = {
        "level": "INFO",
        "class": "logging.handlers.RotatingFileHandler",
        "filename": BASE_DIR / "logs" / "django.json",
        "maxBytes": 1024 * 1024 * 15,  # 15MB
        "backupCount": 10,
        "formatter": "json",
        "filters": ["request_id"],
    }
    
    # Update loggers to use JSON logging
    for logger_name in ["django", "payments", "orders", "accounts"]:
        if logger_name in LOGGING["loggers"]:
            LOGGING["loggers"][logger_name]["handlers"].append("json_file")

# -----------------------------------------------------------------------------
# Error Monitoring (Sentry)
# -----------------------------------------------------------------------------
SENTRY_DSN = os.getenv("SENTRY_DSN")
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            DjangoIntegration(transaction_style="url"),
            CeleryIntegration(),
            RedisIntegration(),
        ],
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
        send_default_pii=False,
        environment=os.getenv("ENVIRONMENT", "production"),
        release=os.getenv("APP_VERSION", "unknown"),
    )

# -----------------------------------------------------------------------------
# Performance Monitoring
# -----------------------------------------------------------------------------
# Database query logging in production (disabled by default)
if os.getenv("LOG_DB_QUERIES", "0") == "1":
    LOGGING["loggers"]["django.db.backends"] = {
        "handlers": ["file"],
        "level": "DEBUG",
        "propagate": False,
    }

# -----------------------------------------------------------------------------
# API Configuration (Production)
# -----------------------------------------------------------------------------
# Strict API settings
REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"] = [
    "rest_framework.permissions.IsAuthenticated",
]

# Production throttle rates
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
    "anon": os.getenv("DRF_ANON_THROTTLE_RATE", "100/hour"),
    "user": os.getenv("DRF_USER_THROTTLE_RATE", "1000/hour"),
    "login": "5/min",
    "register": "3/min",
}

# Remove browsable API in production
REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = [
    "rest_framework.renderers.JSONRenderer",
]

# -----------------------------------------------------------------------------
# CORS Configuration (Production)
# -----------------------------------------------------------------------------
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = _split_csv("CORS_ALLOWED_ORIGINS")
if not CORS_ALLOWED_ORIGINS:
    raise ValueError("CORS_ALLOWED_ORIGINS must be set in production")

# Strict CORS headers
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
]

# -----------------------------------------------------------------------------
# Celery Configuration (Production)
# -----------------------------------------------------------------------------
# Production Celery settings
CELERY_TASK_ALWAYS_EAGER = False
CELERY_TASK_EAGER_PROPAGATES = False
CELERY_WORKER_HIJACK_ROOT_LOGGER = False
CELERY_WORKER_LOG_FORMAT = "[%(asctime)s: %(levelname)s/%(processName)s] %(message)s"
CELERY_WORKER_TASK_LOG_FORMAT = "[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s"

# -----------------------------------------------------------------------------
# File Upload Security (Production)
# -----------------------------------------------------------------------------
# Strict file upload settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024  # 2MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024  # 2MB
FILE_UPLOAD_PERMISSIONS = 0o644
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o755

# Allowed file extensions
ALLOWED_IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
ALLOWED_DOCUMENT_EXTENSIONS = ['.pdf', '.doc', '.docx', '.txt']

# -----------------------------------------------------------------------------
# Admin Security (Production)
# -----------------------------------------------------------------------------
# Secure admin settings
ADMIN_URL = os.getenv("ADMIN_URL", "admin/")
if ADMIN_URL == "admin/":
    import warnings
    warnings.warn("Using default admin URL in production is not recommended")

# -----------------------------------------------------------------------------
# Health Checks
# -----------------------------------------------------------------------------
HEALTH_CHECK_PROVIDERS = {
    "database": "health_check.db.backends.DatabaseBackend",
    "cache": "health_check.cache.backends.CacheBackend",
    "storage": "health_check.storage.backends.DefaultFileStorageHealthCheck",
}

if "health_check" not in INSTALLED_APPS:
    INSTALLED_APPS.append("health_check")
    INSTALLED_APPS.append("health_check.db")
    INSTALLED_APPS.append("health_check.cache")
    INSTALLED_APPS.append("health_check.storage")

# -----------------------------------------------------------------------------
# Validation
# -----------------------------------------------------------------------------
# Validate critical settings
required_settings = [
    "SECRET_KEY",
    "ALLOWED_HOSTS",
    "CORS_ALLOWED_ORIGINS",
]

for setting in required_settings:
    if not globals().get(setting):
        raise ValueError(f"{setting} must be set in production")

# Validate external services
if not STRIPE_SECRET_KEY:
    import warnings
    warnings.warn("Stripe configuration is missing")

print("\n" + "="*50)
print("PRODUCTION SETTINGS LOADED")
print(f"DEBUG: {DEBUG}")
print(f"ALLOWED_HOSTS: {ALLOWED_HOSTS}")
print(f"DATABASE: {DATABASES['default']['ENGINE']}")
print(f"CACHE: {CACHES['default']['BACKEND']}")
print(f"SENTRY: {'Enabled' if SENTRY_DSN else 'Disabled'}")
print("="*50 + "\n")
