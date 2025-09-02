"""Cache configuration and settings for the RMS application."""

import os
from django.conf import settings

# Cache timeout configurations (in seconds)
CACHE_TIMEOUTS = {
    'DEFAULT': 300,  # 5 minutes
    'MENU': 1800,    # 30 minutes
    'USER': 900,     # 15 minutes
    'API': 300,      # 5 minutes
    'STATIC': 86400, # 24 hours
    'ANALYTICS': 3600, # 1 hour
    'INVENTORY': 600,  # 10 minutes
    'RESERVATIONS': 300, # 5 minutes
    'POPULAR_ITEMS': 1800, # 30 minutes
    'SEARCH': 600,   # 10 minutes
}

# Cache key prefixes
CACHE_PREFIXES = {
    'MENU_ITEMS': 'menu_items',
    'MENU_CATEGORIES': 'menu_categories',
    'USER_PROFILE': 'user_profile',
    'USER_PERMISSIONS': 'user_permissions',
    'USER_ORDERS': 'user_orders',
    'CART_TOTALS': 'cart_totals',
    'POPULAR_ITEMS': 'popular_items',
    'ANALYTICS': 'analytics',
    'INVENTORY': 'inventory',
    'RESERVATIONS': 'reservations',
    'API_TABLES': 'api_tables_data',
    'SEARCH': 'search',
}

# Cache vary headers for different content types
CACHE_VARY_HEADERS = {
    'API': ['Accept', 'Accept-Language', 'Authorization'],
    'USER_CONTENT': ['Cookie', 'Accept-Language'],
    'STATIC': ['Accept-Encoding'],
    'ANONYMOUS': ['Accept-Language'],
}

# Cache control headers
CACHE_CONTROL_HEADERS = {
    'API_SUCCESS': 'public, max-age=300',
    'API_ERROR': 'no-cache, no-store, must-revalidate',
    'USER_PRIVATE': 'private, max-age=300',
    'ANONYMOUS_PUBLIC': 'public, max-age=600',
    'STATIC_CONTENT': 'public, max-age=86400',
}

# Cache invalidation patterns
INVALIDATION_PATTERNS = {
    'MENU': [
        'menu_items:*',
        'menu_categories:*',
        'popular_items:*',
        'search:menu:*'
    ],
    'USER': [
        'user_profile:{user_id}',
        'user_permissions:{user_id}',
        'user_orders:{user_id}',
        'cart_totals:{user_id}:*'
    ],
    'ORDERS': [
        'user_orders:*',
        'popular_items:*',
        'analytics:*'
    ],
    'RESERVATIONS': [
        'reservations:*',
        'api_tables_data',
        'analytics:*'
    ],
    'INVENTORY': [
        'inventory:*',
        'menu_items:*'  # Inventory changes might affect menu availability
    ]
}

# Cache warming configuration
CACHE_WARMUP_CONFIG = {
    'ENABLED': getattr(settings, 'CACHE_WARMUP_ENABLED', True),
    'MENU_ITEMS_LIMIT': 50,  # Number of menu items to pre-cache
    'POPULAR_ITEMS_LIMIT': 20,  # Number of popular items to pre-cache
    'CATEGORIES_ALL': True,  # Cache all categories
    'WARMUP_ON_STARTUP': getattr(settings, 'CACHE_WARMUP_ON_STARTUP', False),
}

# Cache monitoring configuration
CACHE_MONITORING = {
    'ENABLED': getattr(settings, 'CACHE_MONITORING_ENABLED', settings.DEBUG),
    'LOG_CACHE_HITS': True,
    'LOG_CACHE_MISSES': True,
    'LOG_CACHE_INVALIDATIONS': True,
    'PERFORMANCE_HEADERS': settings.DEBUG,
    'DEBUG_TOOLBAR_INTEGRATION': settings.DEBUG,
}

# Cache backend specific configurations
CACHE_BACKEND_CONFIG = {
    'REDIS': {
        'CONNECTION_POOL_KWARGS': {
            'max_connections': 50,
            'retry_on_timeout': True,
        },
        'KEY_PREFIX': getattr(settings, 'CACHE_KEY_PREFIX', 'rms'),
        'VERSION': getattr(settings, 'CACHE_VERSION', 1),
    },
    'MEMCACHED': {
        'KEY_PREFIX': getattr(settings, 'CACHE_KEY_PREFIX', 'rms'),
        'VERSION': getattr(settings, 'CACHE_VERSION', 1),
    },
    'DATABASE': {
        'TABLE': 'cache_table',
        'MAX_ENTRIES': 10000,
    },
    'LOCMEM': {
        'MAX_ENTRIES': 1000,
    }
}

# Environment-specific cache settings
def get_cache_config():
    """Get cache configuration based on environment."""
    
    # Production cache configuration
    if not settings.DEBUG:
        return {
            'default': {
                'BACKEND': 'django_redis.cache.RedisCache',
                'LOCATION': os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/1'),
                'OPTIONS': {
                    'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                    'CONNECTION_POOL_KWARGS': CACHE_BACKEND_CONFIG['REDIS']['CONNECTION_POOL_KWARGS'],
                    'COMPRESSOR': 'django_redis.compressors.zlib.ZlibCompressor',
                    'SERIALIZER': 'django_redis.serializers.json.JSONSerializer',
                },
                'KEY_PREFIX': CACHE_BACKEND_CONFIG['REDIS']['KEY_PREFIX'],
                'VERSION': CACHE_BACKEND_CONFIG['REDIS']['VERSION'],
                'TIMEOUT': CACHE_TIMEOUTS['DEFAULT'],
            }
        }
    
    # Development cache configuration
    else:
        return {
            'default': {
                'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
                'LOCATION': 'rms-cache',
                'OPTIONS': {
                    'MAX_ENTRIES': CACHE_BACKEND_CONFIG['LOCMEM']['MAX_ENTRIES'],
                },
                'TIMEOUT': CACHE_TIMEOUTS['DEFAULT'],
            }
        }

# Cache key generation utilities
def generate_cache_key(prefix, *args, **kwargs):
    """Generate a standardized cache key."""
    key_parts = [prefix]
    
    # Add positional arguments
    for arg in args:
        if arg is not None:
            key_parts.append(str(arg))
    
    # Add keyword arguments
    for key, value in sorted(kwargs.items()):
        if value is not None:
            key_parts.append(f"{key}:{value}")
    
    return ':'.join(key_parts)

# Cache condition utilities
def should_cache_request(request):
    """Determine if a request should be cached."""
    
    # Don't cache if user is staff/admin
    if hasattr(request, 'user') and request.user.is_authenticated:
        if request.user.is_staff or request.user.is_superuser:
            return False
    
    # Don't cache POST/PUT/PATCH/DELETE requests
    if request.method not in ['GET', 'HEAD']:
        return False
    
    # Don't cache if there are query parameters (except specific ones)
    allowed_params = ['page', 'limit', 'category', 'search']
    query_params = set(request.GET.keys())
    if query_params and not query_params.issubset(allowed_params):
        return False
    
    return True

def get_cache_timeout(cache_type):
    """Get cache timeout for a specific cache type."""
    return CACHE_TIMEOUTS.get(cache_type.upper(), CACHE_TIMEOUTS['DEFAULT'])

def get_cache_key_prefix(prefix_type):
    """Get cache key prefix for a specific type."""
    return CACHE_PREFIXES.get(prefix_type.upper(), prefix_type.lower())

def get_vary_headers(content_type):
    """Get vary headers for a specific content type."""
    return CACHE_VARY_HEADERS.get(content_type.upper(), [])

def get_cache_control_header(header_type):
    """Get cache control header for a specific type."""
    return CACHE_CONTROL_HEADERS.get(header_type.upper(), 'no-cache')