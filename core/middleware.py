# core/middleware.py
from __future__ import annotations

import logging
import traceback
from typing import Callable, Any

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse, HttpResponsePermanentRedirect
from django.shortcuts import render
from django.utils.deprecation import MiddlewareMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.db import DatabaseError, IntegrityError
from django.core.cache import cache
from django.utils import timezone

# Get loggers
logger = logging.getLogger(__name__)
security_logger = logging.getLogger('django.security')
error_logger = logging.getLogger('django.request')


class CanonicalHostMiddleware:
    """
    Redirects all requests to settings.CANONICAL_HOST (no scheme).
    Enabled when CANONICAL_HOST is set and DEBUG=False.
    """
    def __init__(self, get_response):
        self.get_response = get_response
        self.host = getattr(settings, "CANONICAL_HOST", "").strip()

    def __call__(self, request):
        if not self.host:
            return self.get_response(request)
        incoming = request.get_host()
        in_host = incoming.split(":")[0]
        if in_host.lower() != self.host.lower():
            return HttpResponsePermanentRedirect(f"https://{self.host}{request.get_full_path()}")
        return self.get_response(request)


class ErrorHandlingMiddleware(MiddlewareMixin):
    """
    Comprehensive error handling middleware that:
    1. Logs all errors with context
    2. Returns appropriate error responses
    3. Tracks error patterns for security monitoring
    4. Provides consistent error formatting
    """
    
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response
        super().__init__(get_response)
    
    def process_exception(self, request: HttpRequest, exception: Exception) -> HttpResponse | None:
        """
        Process exceptions and return appropriate error responses.
        """
        # Get client IP for logging
        client_ip = self._get_client_ip(request)
        user_id = getattr(request.user, 'id', None) if hasattr(request, 'user') and request.user.is_authenticated else None
        
        # Create error context
        error_context = {
            'url': request.get_full_path(),
            'method': request.method,
            'client_ip': client_ip,
            'user_id': user_id,
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'timestamp': timezone.now().isoformat(),
        }
        
        # Handle different exception types
        if isinstance(exception, Http404):
            return self._handle_404(request, exception, error_context)
        elif isinstance(exception, PermissionDenied):
            return self._handle_403(request, exception, error_context)
        elif isinstance(exception, ValidationError):
            return self._handle_400(request, exception, error_context)
        elif isinstance(exception, (DatabaseError, IntegrityError)):
            return self._handle_database_error(request, exception, error_context)
        else:
            return self._handle_500(request, exception, error_context)
    
    def _handle_404(self, request: HttpRequest, exception: Exception, context: dict) -> HttpResponse:
        """
        Handle 404 Not Found errors.
        """
        logger.info(f"404 Not Found: {context['url']} from {context['client_ip']}")
        
        # Track suspicious 404 patterns (potential scanning)
        self._track_suspicious_activity(request, '404_pattern')
        
        if self._is_api_request(request):
            return JsonResponse({
                'error': 'Not Found',
                'message': 'The requested resource was not found.',
                'status_code': 404
            }, status=404)
        
        return render(request, 'storefront/404.html', status=404)
    
    def _handle_403(self, request: HttpRequest, exception: Exception, context: dict) -> HttpResponse:
        """
        Handle 403 Forbidden errors.
        """
        security_logger.warning(
            f"403 Forbidden: {context['url']} from {context['client_ip']} "
            f"(User: {context['user_id']}) - {str(exception)}"
        )
        
        # Track unauthorized access attempts
        self._track_suspicious_activity(request, 'unauthorized_access')
        
        if self._is_api_request(request):
            return JsonResponse({
                'error': 'Forbidden',
                'message': 'You do not have permission to access this resource.',
                'status_code': 403
            }, status=403)
        
        return render(request, 'storefront/403.html', status=403)
    
    def _handle_400(self, request: HttpRequest, exception: Exception, context: dict) -> HttpResponse:
        """
        Handle 400 Bad Request errors (ValidationError).
        """
        logger.warning(
            f"400 Bad Request: {context['url']} from {context['client_ip']} - {str(exception)}"
        )
        
        if self._is_api_request(request):
            error_details = []
            if hasattr(exception, 'error_dict'):
                # Field-specific validation errors
                for field, errors in exception.error_dict.items():
                    for error in errors:
                        error_details.append(f"{field}: {error.message}")
            elif hasattr(exception, 'error_list'):
                # Non-field validation errors
                for error in exception.error_list:
                    error_details.append(error.message)
            else:
                error_details.append(str(exception))
            
            return JsonResponse({
                'error': 'Bad Request',
                'message': 'Invalid input data.',
                'details': error_details,
                'status_code': 400
            }, status=400)
        
        return render(request, 'storefront/400.html', status=400)
    
    def _handle_database_error(self, request: HttpRequest, exception: Exception, context: dict) -> HttpResponse:
        """
        Handle database-related errors.
        """
        error_logger.error(
            f"Database Error: {context['url']} from {context['client_ip']} - {str(exception)}\n"
            f"Traceback: {traceback.format_exc()}"
        )
        
        # Don't expose database details in production
        if settings.DEBUG:
            error_message = str(exception)
        else:
            error_message = "A database error occurred. Please try again later."
        
        if self._is_api_request(request):
            return JsonResponse({
                'error': 'Database Error',
                'message': error_message,
                'status_code': 500
            }, status=500)
        
        return render(request, 'storefront/500.html', status=500)
    
    def _handle_500(self, request: HttpRequest, exception: Exception, context: dict) -> HttpResponse:
        """
        Handle 500 Internal Server Error.
        """
        error_logger.error(
            f"500 Internal Server Error: {context['url']} from {context['client_ip']} "
            f"(User: {context['user_id']}) - {str(exception)}\n"
            f"Traceback: {traceback.format_exc()}"
        )
        
        # Don't expose internal details in production
        if settings.DEBUG:
            error_message = str(exception)
        else:
            error_message = "An internal server error occurred. Please try again later."
        
        if self._is_api_request(request):
            return JsonResponse({
                'error': 'Internal Server Error',
                'message': error_message,
                'status_code': 500
            }, status=500)
        
        return render(request, 'storefront/500.html', status=500)
    
    def _is_api_request(self, request: HttpRequest) -> bool:
        """
        Determine if the request is an API request based on headers or path.
        """
        # Check Accept header
        accept_header = request.META.get('HTTP_ACCEPT', '')
        if 'application/json' in accept_header:
            return True
        
        # Check Content-Type header
        content_type = request.META.get('CONTENT_TYPE', '')
        if 'application/json' in content_type:
            return True
        
        # Check URL path
        path = request.path
        api_prefixes = ['/api/', '/accounts/api/', '/orders/api/', '/menu/api/']
        return any(path.startswith(prefix) for prefix in api_prefixes)
    
    def _get_client_ip(self, request: HttpRequest) -> str:
        """
        Get the client's IP address, considering proxy headers.
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', 'unknown')
        return ip
    
    def _track_suspicious_activity(self, request: HttpRequest, activity_type: str) -> None:
        """
        Track suspicious activity patterns for security monitoring.
        """
        client_ip = self._get_client_ip(request)
        cache_key = f"suspicious_activity_{activity_type}_{client_ip}"
        
        # Get current count
        current_count = cache.get(cache_key, 0)
        new_count = current_count + 1
        
        # Store with 1-hour expiration
        cache.set(cache_key, new_count, timeout=3600)
        
        # Log if threshold exceeded
        thresholds = {
            '404_pattern': 20,  # 20 404s in an hour
            'unauthorized_access': 10,  # 10 403s in an hour
        }
        
        threshold = thresholds.get(activity_type, 15)
        if new_count >= threshold:
            security_logger.warning(
                f"Suspicious activity detected: {activity_type} from {client_ip} "
                f"({new_count} occurrences in the last hour)"
            )


class RequestLoggingMiddleware(MiddlewareMixin):
    """
    Middleware to log all requests for monitoring and debugging.
    """
    
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response
        super().__init__(get_response)
    
    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Skip logging for static files and health checks
        if self._should_skip_logging(request):
            return self.get_response(request)
        
        start_time = timezone.now()
        
        # Process request
        response = self.get_response(request)
        
        # Calculate response time
        end_time = timezone.now()
        response_time = (end_time - start_time).total_seconds() * 1000  # in milliseconds
        
        # Log request details
        client_ip = self._get_client_ip(request)
        user_id = getattr(request.user, 'id', None) if hasattr(request, 'user') and request.user.is_authenticated else None
        
        log_data = {
            'method': request.method,
            'path': request.path,
            'status_code': response.status_code,
            'response_time_ms': round(response_time, 2),
            'client_ip': client_ip,
            'user_id': user_id,
            'user_agent': request.META.get('HTTP_USER_AGENT', '')[:200],  # Truncate long user agents
        }
        
        # Log at appropriate level based on status code
        if response.status_code >= 500:
            logger.error(f"Request failed: {log_data}")
        elif response.status_code >= 400:
            logger.warning(f"Client error: {log_data}")
        else:
            logger.info(f"Request completed: {log_data}")
        
        return response
    
    def _should_skip_logging(self, request: HttpRequest) -> bool:
        """
        Determine if we should skip logging for this request.
        """
        skip_paths = [
            '/static/',
            '/media/',
            '/favicon.ico',
            '/health/',
            '/ping/',
        ]
        
        return any(request.path.startswith(path) for path in skip_paths)
    
    def _get_client_ip(self, request: HttpRequest) -> str:
        """
        Get the client's IP address, considering proxy headers.
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', 'unknown')
        return ip
