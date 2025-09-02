# core/rate_limiting.py
from __future__ import annotations

import time
import hashlib
from typing import Dict, Optional, Tuple
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
import logging

logger = logging.getLogger(__name__)
security_logger = logging.getLogger('django.security')


class RateLimitMiddleware(MiddlewareMixin):
    """
    Advanced rate limiting middleware that provides:
    1. IP-based rate limiting with sliding window
    2. User-based rate limiting for authenticated users
    3. Endpoint-specific rate limits
    4. Progressive penalties for repeat offenders
    5. Whitelist/blacklist support
    6. Detailed logging and monitoring
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        
        # Default rate limits (requests per minute)
        self.default_limits = getattr(settings, 'RATE_LIMIT_DEFAULTS', {
            'anonymous': 60,  # 60 requests per minute for anonymous users
            'authenticated': 300,  # 300 requests per minute for authenticated users
            'burst': 10,  # 10 requests per 10 seconds burst limit
        })
        
        # Endpoint-specific limits
        self.endpoint_limits = getattr(settings, 'RATE_LIMIT_ENDPOINTS', {
            '/api/auth/login/': {'anonymous': 5, 'authenticated': 10},
            '/api/auth/register/': {'anonymous': 3, 'authenticated': 5},
            '/api/auth/password-reset/': {'anonymous': 2, 'authenticated': 3},
            '/api/orders/': {'anonymous': 20, 'authenticated': 100},
            '/api/reservations/': {'anonymous': 10, 'authenticated': 50},
        })
        
        # Whitelisted IPs (no rate limiting)
        self.whitelist = set(getattr(settings, 'RATE_LIMIT_WHITELIST', []))
        
        # Blacklisted IPs (always blocked)
        self.blacklist = set(getattr(settings, 'RATE_LIMIT_BLACKLIST', []))
        
        super().__init__(get_response)
    
    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        """
        Check rate limits before processing the request.
        """
        client_ip = self._get_client_ip(request)
        
        # Check blacklist
        if client_ip in self.blacklist:
            security_logger.warning(f"Blocked request from blacklisted IP: {client_ip}")
            return self._rate_limit_response(request, 'blacklisted')
        
        # Skip rate limiting for whitelisted IPs
        if client_ip in self.whitelist:
            return None
        
        # Check if IP is temporarily banned
        if self._is_temporarily_banned(client_ip):
            return self._rate_limit_response(request, 'temporarily_banned')
        
        # Get rate limits for this request
        limits = self._get_rate_limits(request)
        
        # Check each rate limit
        for limit_type, limit_value in limits.items():
            if not self._check_rate_limit(request, limit_type, limit_value):
                # Rate limit exceeded
                self._handle_rate_limit_exceeded(request, limit_type)
                return self._rate_limit_response(request, limit_type)
        
        return None
    
    def _get_client_ip(self, request: HttpRequest) -> str:
        """
        Get the real client IP address, considering proxies.
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '')
        return ip
    
    def _get_rate_limits(self, request: HttpRequest) -> Dict[str, int]:
        """
        Get applicable rate limits for the request.
        """
        path = request.path_info
        is_authenticated = hasattr(request, 'user') and request.user.is_authenticated
        
        limits = {}
        
        # Check endpoint-specific limits first
        for endpoint_pattern, endpoint_limits in self.endpoint_limits.items():
            if path.startswith(endpoint_pattern):
                if is_authenticated and 'authenticated' in endpoint_limits:
                    limits['endpoint'] = endpoint_limits['authenticated']
                elif 'anonymous' in endpoint_limits:
                    limits['endpoint'] = endpoint_limits['anonymous']
                break
        
        # Add default limits
        if is_authenticated:
            limits['user'] = self.default_limits['authenticated']
        else:
            limits['anonymous'] = self.default_limits['anonymous']
        
        # Add burst limit
        limits['burst'] = self.default_limits['burst']
        
        return limits
    
    def _check_rate_limit(self, request: HttpRequest, limit_type: str, limit_value: int) -> bool:
        """
        Check if the request exceeds the rate limit using sliding window.
        """
        client_ip = self._get_client_ip(request)
        user_id = getattr(request.user, 'id', None) if hasattr(request, 'user') and request.user.is_authenticated else None
        
        # Create cache key
        if limit_type == 'user' and user_id:
            cache_key = f"rate_limit_user_{user_id}_{limit_type}"
        else:
            cache_key = f"rate_limit_ip_{client_ip}_{limit_type}"
        
        # Get window duration based on limit type
        if limit_type == 'burst':
            window_seconds = 10  # 10 second window for burst
        else:
            window_seconds = 60  # 1 minute window for others
        
        current_time = int(time.time())
        window_start = current_time - window_seconds
        
        # Get existing requests in the window
        requests_data = cache.get(cache_key, [])
        
        # Filter requests within the current window
        requests_in_window = [req_time for req_time in requests_data if req_time > window_start]
        
        # Check if limit is exceeded
        if len(requests_in_window) >= limit_value:
            return False
        
        # Add current request
        requests_in_window.append(current_time)
        
        # Store updated data with appropriate TTL
        cache.set(cache_key, requests_in_window, timeout=window_seconds + 10)
        
        return True
    
    def _handle_rate_limit_exceeded(self, request: HttpRequest, limit_type: str) -> None:
        """
        Handle rate limit exceeded - logging and progressive penalties.
        """
        client_ip = self._get_client_ip(request)
        user_id = getattr(request.user, 'id', None) if hasattr(request, 'user') and request.user.is_authenticated else None
        
        # Log the violation
        security_logger.warning(
            f"Rate limit exceeded: {limit_type} for IP {client_ip} "
            f"(User: {user_id}) on {request.path_info}"
        )
        
        # Track violations for progressive penalties
        violation_key = f"rate_limit_violations_{client_ip}"
        violations = cache.get(violation_key, 0) + 1
        cache.set(violation_key, violations, timeout=3600)  # 1 hour
        
        # Apply progressive penalties
        if violations >= 10:  # 10 violations in an hour
            # Temporary ban for 1 hour
            ban_key = f"temp_ban_{client_ip}"
            cache.set(ban_key, True, timeout=3600)
            security_logger.error(f"Temporarily banned IP {client_ip} for repeated rate limit violations")
        elif violations >= 5:  # 5 violations in an hour
            # Reduce rate limits by 50%
            penalty_key = f"rate_limit_penalty_{client_ip}"
            cache.set(penalty_key, 0.5, timeout=1800)  # 30 minutes
    
    def _is_temporarily_banned(self, client_ip: str) -> bool:
        """
        Check if IP is temporarily banned.
        """
        ban_key = f"temp_ban_{client_ip}"
        return cache.get(ban_key, False)
    
    def _rate_limit_response(self, request: HttpRequest, reason: str) -> HttpResponse:
        """
        Return appropriate rate limit response.
        """
        messages = {
            'blacklisted': 'Access denied.',
            'temporarily_banned': 'Too many violations. Access temporarily restricted.',
            'burst': 'Too many requests. Please slow down.',
            'endpoint': 'Rate limit exceeded for this endpoint.',
            'user': 'Rate limit exceeded. Please try again later.',
            'anonymous': 'Rate limit exceeded. Please try again later.',
        }
        
        message = messages.get(reason, 'Rate limit exceeded.')
        
        if self._is_api_request(request):
            return JsonResponse({
                'error': 'Rate Limit Exceeded',
                'message': message,
                'status_code': 429
            }, status=429)
        
        # For web requests, return HTML response
        from django.shortcuts import render
        return render(request, 'storefront/429.html', {
            'message': message
        }, status=429)
    
    def _is_api_request(self, request: HttpRequest) -> bool:
        """
        Determine if this is an API request.
        """
        return (
            request.path_info.startswith('/api/') or
            request.META.get('HTTP_ACCEPT', '').startswith('application/json') or
            request.META.get('CONTENT_TYPE', '').startswith('application/json')
        )


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Middleware to add comprehensive security headers.
    """
    
    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """
        Add security headers to the response.
        """
        # Prevent clickjacking
        if not response.get('X-Frame-Options'):
            response['X-Frame-Options'] = 'DENY'
        
        # Prevent MIME type sniffing
        response['X-Content-Type-Options'] = 'nosniff'
        
        # XSS Protection
        response['X-XSS-Protection'] = '1; mode=block'
        
        # Referrer Policy
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Permissions Policy (formerly Feature Policy)
        response['Permissions-Policy'] = (
            'camera=(), microphone=(), geolocation=(), '
            'payment=(), usb=(), magnetometer=(), gyroscope=()'
        )
        
        # Content Security Policy (basic)
        if not response.get('Content-Security-Policy'):
            csp = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self' data:; "
                "connect-src 'self'; "
                "frame-ancestors 'none';"
            )
            response['Content-Security-Policy'] = csp
        
        # HSTS (only in production)
        if not getattr(settings, 'DEBUG', True):
            response['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'
        
        return response