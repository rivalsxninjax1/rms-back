# rms_backend/settings/__init__.py
"""
Django settings package for RMS Backend.

This package provides environment-specific settings:
- development: Local development with debug enabled
- staging: Production-like environment for testing
- production: Production environment with security hardening

Settings are automatically loaded based on the DJANGO_SETTINGS_MODULE
environment variable or default to development.
"""

import os
import sys
from pathlib import Path

# Determine which settings to load
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()

# Validate environment
VALID_ENVIRONMENTS = ["development", "staging", "production"]
if ENVIRONMENT not in VALID_ENVIRONMENTS:
    raise ValueError(
        f"Invalid ENVIRONMENT '{ENVIRONMENT}'. "
        f"Must be one of: {', '.join(VALID_ENVIRONMENTS)}"
    )

# Load appropriate settings
try:
    if ENVIRONMENT == "production":
        from .production import *
        print(f"🚀 Loaded PRODUCTION settings")
    elif ENVIRONMENT == "staging":
        from .staging import *
        print(f"🧪 Loaded STAGING settings")
    else:
        from .development import *
        print(f"🛠️  Loaded DEVELOPMENT settings")
except ImportError as e:
    print(f"❌ Error loading {ENVIRONMENT} settings: {e}")
    # Fallback to development settings
    if ENVIRONMENT != "development":
        print("📋 Falling back to development settings")
        from .development import *
    else:
        raise

# Add environment info to settings
ENVIRONMENT_INFO = {
    "name": ENVIRONMENT,
    "debug": DEBUG,
    "allowed_hosts": ALLOWED_HOSTS,
    "database_engine": DATABASES["default"]["ENGINE"],
    "cache_backend": CACHES["default"]["BACKEND"],
    "static_url": STATIC_URL,
    "media_url": MEDIA_URL,
}

# Validate critical settings
def validate_settings():
    """Validate critical settings are properly configured."""
    errors = []
    
    # Check SECRET_KEY
    if not SECRET_KEY or SECRET_KEY == "your-secret-key-here":
        errors.append("SECRET_KEY must be set to a secure random value")
    
    # Check database configuration
    if not DATABASES.get("default"):
        errors.append("Database configuration is missing")
    
    # Check allowed hosts in production
    if ENVIRONMENT == "production" and not ALLOWED_HOSTS:
        errors.append("ALLOWED_HOSTS must be configured for production")
    
    # Check CORS configuration
    if ENVIRONMENT == "production" and globals().get("CORS_ALLOW_ALL_ORIGINS", False):
        errors.append("CORS_ALLOW_ALL_ORIGINS should not be True in production")
    
    # Check debug setting
    if ENVIRONMENT == "production" and DEBUG:
        errors.append("DEBUG should be False in production")
    
    if errors:
        error_msg = "\n".join([f"  - {error}" for error in errors])
        raise ValueError(f"Settings validation failed:\n{error_msg}")

# Run validation
if "migrate" not in sys.argv and "collectstatic" not in sys.argv:
    try:
        validate_settings()
        print(f"✅ Settings validation passed for {ENVIRONMENT} environment")
    except ValueError as e:
        print(f"⚠️  Settings validation warning: {e}")
        if ENVIRONMENT == "production":
            raise

# Export environment info for debugging
__all__ = ["ENVIRONMENT_INFO", "validate_settings"]