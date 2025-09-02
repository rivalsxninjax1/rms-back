import time
import logging
from django.core.cache import cache
from django.http import HttpResponse
from django.utils.cache import get_cache_key, learn_cache_key
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
from core.cache_service import CacheService

logger = logging.getLogger(__name__)


class CachePerformanceMiddleware(MiddlewareMixin):
    """Middleware to monitor cache performance and add cache headers."""
    
    def process_request(self, request):
        """Start timing the request and check cache status."""
        request._cache_start_time = time.time()
        request._cache_hits = 0
        request._cache_misses = 0
        
        # Add cache status to request for debugging
        if settings.DEBUG:
            request._cache_debug = True
        
        return None
    
    def process_response(self, request, response):
        """Add cache performance headers and log cache statistics."""
        
        # Calculate request processing time
        if hasattr(request, '_cache_start_time'):
            processing_time = time.time() - request._cache_start_time
            
            # Add performance headers in debug mode
            if settings.DEBUG:
                response['X-Cache-Processing-Time'] = f"{processing_time:.3f}s"
                response['X-Cache-Hits'] = getattr(request, '_cache_hits', 0)
                response['X-Cache-Misses'] = getattr(request, '_cache_misses', 0)
                
                # Add cache backend info
                response['X-Cache-Backend'] = cache.__class__.__name__
        
        # Add cache control headers for static content
        if self._is_static_content(request):
            response['Cache-Control'] = 'public, max-age=86400'  # 24 hours
            response['Vary'] = 'Accept-Encoding'
        
        # Add cache headers for API responses
        elif request.path.startswith('/api/'):
            if response.status_code == 200:
                response['Cache-Control'] = 'public, max-age=300'  # 5 minutes
                response['Vary'] = 'Accept, Accept-Language, Authorization'
            else:
                response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        
        # Add cache headers for authenticated user content
        elif hasattr(request, 'user') and request.user.is_authenticated:
            response['Cache-Control'] = 'private, max-age=300'  # 5 minutes
            response['Vary'] = 'Cookie, Accept-Language'
        
        # Add cache headers for anonymous user content
        else:
            response['Cache-Control'] = 'public, max-age=600'  # 10 minutes
            response['Vary'] = 'Accept-Language'
        
        return response
    
    def _is_static_content(self, request):
        """Check if the request is for static content."""
        static_paths = ['/static/', '/media/', '/favicon.ico']
        return any(request.path.startswith(path) for path in static_paths)


class CacheInvalidationMiddleware(MiddlewareMixin):
    """Middleware to handle cache invalidation on data changes."""
    
    def process_request(self, request):
        """Track request method for cache invalidation."""
        request._original_method = request.method
        return None
    
    def process_response(self, request, response):
        """Invalidate cache on successful data modifications."""
        # Allow turning off cache invalidation globally
        from django.conf import settings
        if getattr(settings, 'CACHE_DISABLED', False):
            return response

        # Only invalidate on successful modifications
        if (request._original_method in ['POST', 'PUT', 'PATCH', 'DELETE'] and 
            200 <= response.status_code < 300):
            
            self._invalidate_relevant_cache(request, response)
        
        return response
    
    def _invalidate_relevant_cache(self, request, response):
        """Invalidate cache based on the request path and method."""
        
        try:
            path = request.path
            
            # Invalidate menu cache on menu modifications
            if '/menu/' in path or '/api/menu/' in path:
                CacheService.invalidate_menu_cache()
                logger.info(f"Invalidated menu cache due to {request.method} {path}")
            
            # Invalidate user cache on user modifications
            elif '/user/' in path or '/api/user/' in path:
                if hasattr(request, 'user') and request.user.is_authenticated:
                    CacheService.invalidate_user_cache(request.user.id)
                    logger.info(f"Invalidated user cache for user {request.user.id}")
            
            # Invalidate order cache on order modifications
            elif '/order/' in path or '/api/order/' in path or '/cart/' in path:
                if hasattr(request, 'user') and request.user.is_authenticated:
                    CacheService.invalidate_user_cache(request.user.id)
                # Also invalidate popular items cache as orders affect popularity
                CacheService.delete_pattern('popular_items:*')
                logger.info(f"Invalidated order-related cache due to {request.method} {path}")
            
            # Invalidate reservation cache on reservation modifications
            elif '/reservation/' in path or '/api/reservation/' in path:
                CacheService.delete_pattern('reservations:*')
                CacheService.delete_pattern('api_tables_data')
                logger.info(f"Invalidated reservation cache due to {request.method} {path}")
            
            # Invalidate inventory cache on inventory modifications
            elif '/inventory/' in path or '/api/inventory/' in path:
                CacheService.delete_pattern('inventory:*')
                logger.info(f"Invalidated inventory cache due to {request.method} {path}")
                
        except Exception as e:
            logger.error(f"Error invalidating cache: {str(e)}")


class CacheCompressionMiddleware(MiddlewareMixin):
    """Middleware to handle cache compression and optimization."""
    
    def process_response(self, request, response):
        """Add compression hints and optimize cache storage."""
        
        # Add compression hints for cacheable responses
        if (response.status_code == 200 and 
            'Cache-Control' in response and 
            'no-cache' not in response['Cache-Control']):
            
            # Add compression hints
            if 'Vary' in response:
                if 'Accept-Encoding' not in response['Vary']:
                    response['Vary'] += ', Accept-Encoding'
            else:
                response['Vary'] = 'Accept-Encoding'
            
            # Add ETag for better caching
            if not response.get('ETag'):
                content_hash = hash(response.content)
                response['ETag'] = f'W/"{content_hash}"'
        
        return response


class CacheDebugMiddleware(MiddlewareMixin):
    """Middleware to add cache debugging information in development."""
    
    def process_request(self, request):
        """Initialize cache debug tracking."""
        if settings.DEBUG:
            request._cache_operations = []
            
            # Monkey patch cache operations to track them
            original_get = cache.get
            original_set = cache.set
            original_delete = cache.delete
            
            def tracked_get(key, default=None, version=None):
                result = original_get(key, default, version)
                request._cache_operations.append({
                    'operation': 'GET',
                    'key': key,
                    'hit': result is not None and result != default,
                    'timestamp': time.time()
                })
                return result
            
            def tracked_set(key, value, timeout=None, version=None):
                result = original_set(key, value, timeout, version)
                request._cache_operations.append({
                    'operation': 'SET',
                    'key': key,
                    'timeout': timeout,
                    'timestamp': time.time()
                })
                return result
            
            def tracked_delete(key, version=None):
                result = original_delete(key, version)
                request._cache_operations.append({
                    'operation': 'DELETE',
                    'key': key,
                    'timestamp': time.time()
                })
                return result
            
            cache.get = tracked_get
            cache.set = tracked_set
            cache.delete = tracked_delete
            
            request._original_cache_methods = {
                'get': original_get,
                'set': original_set,
                'delete': original_delete
            }
        
        return None
    
    def process_response(self, request, response):
        """Add cache debug information to response."""
        
        if settings.DEBUG and hasattr(request, '_cache_operations'):
            # Restore original cache methods
            if hasattr(request, '_original_cache_methods'):
                cache.get = request._original_cache_methods['get']
                cache.set = request._original_cache_methods['set']
                cache.delete = request._original_cache_methods['delete']
            
            # Add debug headers
            operations = request._cache_operations
            response['X-Cache-Operations-Count'] = len(operations)
            response['X-Cache-Gets'] = len([op for op in operations if op['operation'] == 'GET'])
            response['X-Cache-Sets'] = len([op for op in operations if op['operation'] == 'SET'])
            response['X-Cache-Deletes'] = len([op for op in operations if op['operation'] == 'DELETE'])
            response['X-Cache-Hit-Rate'] = (
                len([op for op in operations if op['operation'] == 'GET' and op.get('hit', False)]) / 
                max(len([op for op in operations if op['operation'] == 'GET']), 1) * 100
            )
        
        return response
