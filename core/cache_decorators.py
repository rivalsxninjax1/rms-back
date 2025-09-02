from functools import wraps
from typing import Any, Callable, Optional, Union
from django.core.cache import cache
from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils.cache import get_cache_key
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_headers
import hashlib
import json


# Cache timeouts (in seconds)
DEFAULT_CACHE_TIMEOUT = getattr(settings, 'DEFAULT_CACHE_TIMEOUT', 300)  # 5 minutes
MENU_CACHE_TIMEOUT = getattr(settings, 'MENU_CACHE_TIMEOUT', 3600)  # 1 hour
USER_CACHE_TIMEOUT = getattr(settings, 'USER_CACHE_TIMEOUT', 900)  # 15 minutes
API_CACHE_TIMEOUT = getattr(settings, 'API_CACHE_TIMEOUT', 600)  # 10 minutes
STATIC_CACHE_TIMEOUT = getattr(settings, 'STATIC_CACHE_TIMEOUT', 86400)  # 24 hours


def cache_key_generator(prefix: str, *args, **kwargs) -> str:
    """
    Generate a consistent cache key from arguments.
    """
    key_data = {
        'args': args,
        'kwargs': sorted(kwargs.items()) if kwargs else None
    }
    key_string = json.dumps(key_data, sort_keys=True, default=str)
    key_hash = hashlib.md5(key_string.encode()).hexdigest()[:12]
    return f"{prefix}:{key_hash}"


def cache_result(timeout: int = DEFAULT_CACHE_TIMEOUT, key_prefix: str = 'result'):
    """
    Decorator to cache function results.
    
    Args:
        timeout: Cache timeout in seconds
        key_prefix: Prefix for cache key
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = cache_key_generator(f"{key_prefix}:{func.__name__}", *args, **kwargs)
            
            # Try to get from cache
            result = cache.get(cache_key)
            if result is not None:
                return result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, timeout)
            return result
        return wrapper
    return decorator


def cache_user_data(timeout: int = USER_CACHE_TIMEOUT):
    """
    Decorator to cache user-specific data.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(request: HttpRequest, *args, **kwargs):
            if not hasattr(request, 'user') or not request.user.is_authenticated:
                return func(request, *args, **kwargs)
            
            # Generate user-specific cache key
            cache_key = cache_key_generator(
                f"user_data:{func.__name__}",
                request.user.id,
                *args,
                **kwargs
            )
            
            # Try to get from cache
            result = cache.get(cache_key)
            if result is not None:
                return result
            
            # Execute function and cache result
            result = func(request, *args, **kwargs)
            cache.set(cache_key, result, timeout)
            return result
        return wrapper
    return decorator


def cache_menu_data(timeout: int = MENU_CACHE_TIMEOUT):
    """
    Decorator specifically for menu-related data caching.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate menu-specific cache key
            cache_key = cache_key_generator(f"menu:{func.__name__}", *args, **kwargs)
            
            # Try to get from cache
            result = cache.get(cache_key)
            if result is not None:
                return result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, timeout)
            return result
        return wrapper
    return decorator


def cache_api_response(timeout: int = API_CACHE_TIMEOUT, vary_on: Optional[list] = None):
    """
    Decorator for caching API responses with optional vary headers.
    
    Args:
        timeout: Cache timeout in seconds
        vary_on: List of headers to vary cache on (e.g., ['Accept-Language', 'Authorization'])
    """
    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def wrapper(request: HttpRequest, *args, **kwargs):
            # Generate cache key including vary headers
            vary_data = {}
            if vary_on:
                for header in vary_on:
                    vary_data[header] = request.META.get(f'HTTP_{header.upper().replace("-", "_")}')
            
            cache_key = cache_key_generator(
                f"api:{view_func.__name__}",
                request.method,
                request.path,
                request.GET.urlencode(),
                vary_data,
                *args,
                **kwargs
            )
            
            # Try to get from cache
            cached_response = cache.get(cache_key)
            if cached_response is not None:
                return cached_response
            
            # Execute view and cache response
            response = view_func(request, *args, **kwargs)
            
            # Only cache successful responses
            if hasattr(response, 'status_code') and 200 <= response.status_code < 300:
                cache.set(cache_key, response, timeout)
            
            return response
        return wrapper
    return decorator


def invalidate_cache_pattern(pattern: str):
    """
    Invalidate all cache keys matching a pattern.
    
    Args:
        pattern: Cache key pattern to match (e.g., 'menu:*', 'user_data:123:*')
    """
    try:
        # Check if we're using Redis cache backend
        if hasattr(cache._cache, 'get_client'):
            redis_client = cache._cache.get_client()
            key_prefix = settings.CACHES['default'].get('KEY_PREFIX', '')
            search_pattern = f"{key_prefix}:*:{pattern}" if key_prefix else f"*:{pattern}"
            keys = redis_client.keys(search_pattern)
            if keys:
                redis_client.delete(*keys)
                return len(keys)
        else:
            # For non-Redis backends (like LocMemCache), pattern deletion is not supported
            pass
    except Exception:
        # Fallback for non-Redis backends
        pass
    return 0


def invalidate_user_cache(user_id: int):
    """
    Invalidate all cache entries for a specific user.
    """
    return invalidate_cache_pattern(f"user_data:*:{user_id}:*")


def invalidate_menu_cache():
    """
    Invalidate all menu-related cache entries.
    """
    return invalidate_cache_pattern("menu:*")


def invalidate_api_cache(view_name: str = None):
    """
    Invalidate API cache entries.
    
    Args:
        view_name: Specific view name to invalidate, or None for all API cache
    """
    pattern = f"api:{view_name}:*" if view_name else "api:*"
    return invalidate_cache_pattern(pattern)


# Convenience decorators for common use cases
def cache_page_conditional(timeout: int, condition: Callable[[HttpRequest], bool]):
    """
    Cache page only if condition is met.
    
    Args:
        timeout: Cache timeout in seconds
        condition: Function that takes request and returns boolean
    """
    def decorator(view_func: Callable) -> Callable:
        cached_view = cache_page(timeout)(view_func)
        
        @wraps(view_func)
        def wrapper(request: HttpRequest, *args, **kwargs):
            if condition(request):
                return cached_view(request, *args, **kwargs)
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


# Common condition functions
def is_anonymous_user(request: HttpRequest) -> bool:
    """Check if user is anonymous (for caching anonymous-only content)."""
    return not request.user.is_authenticated


def is_get_request(request: HttpRequest) -> bool:
    """Check if request is GET method."""
    return request.method == 'GET'


def has_no_query_params(request: HttpRequest) -> bool:
    """Check if request has no query parameters."""
    return not request.GET


# Template tag helpers
class CacheHelper:
    """
    Helper class for template-level caching operations.
    """
    
    @staticmethod
    def get_fragment_key(fragment_name: str, *args) -> str:
        """Generate cache key for template fragments."""
        return cache_key_generator(f"fragment:{fragment_name}", *args)
    
    @staticmethod
    def cache_fragment(fragment_name: str, timeout: int = DEFAULT_CACHE_TIMEOUT, *args):
        """Cache template fragment with given name and arguments."""
        cache_key = CacheHelper.get_fragment_key(fragment_name, *args)
        return cache_key, timeout
    
    @staticmethod
    def invalidate_fragment(fragment_name: str, *args):
        """Invalidate specific template fragment."""
        cache_key = CacheHelper.get_fragment_key(fragment_name, *args)
        cache.delete(cache_key)