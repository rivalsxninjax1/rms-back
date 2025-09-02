from __future__ import annotations

import json
from typing import Any

from django.http import HttpRequest, HttpResponse
from django.contrib.auth.models import AnonymousUser
from django.utils.deprecation import MiddlewareMixin
from django.contrib.contenttypes.models import ContentType

from .models import AuditLog


class AuditLogMiddleware(MiddlewareMixin):
    """
    Middleware to automatically log admin actions and API requests.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
    
    def process_request(self, request: HttpRequest) -> None:
        """Store request data for later use in response processing."""
        # Store original request data
        request._audit_data = {
            'method': request.method,
            'path': request.path,
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'ip_address': self._get_client_ip(request),
        }
        
        # Store request body for POST/PUT/PATCH requests
        if request.method in ['POST', 'PUT', 'PATCH'] and hasattr(request, 'body'):
            try:
                request._audit_data['request_body'] = request.body.decode('utf-8')
            except (UnicodeDecodeError, AttributeError):
                request._audit_data['request_body'] = '<binary data>'
    
    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """Log the request/response if it's an admin action."""
        # Only log for authenticated admin users
        if (hasattr(request, 'user') and 
            not isinstance(request.user, AnonymousUser) and 
            request.user.is_staff and 
            hasattr(request, '_audit_data')):
            
            # Log API requests to admin endpoints
            if self._should_log_request(request, response):
                self._log_request(request, response)
        
        return response
    
    def _should_log_request(self, request: HttpRequest, response: HttpResponse) -> bool:
        """Determine if this request should be logged."""
        path = request.path
        method = request.method
        
        # Log admin API endpoints
        admin_endpoints = [
            '/api/reports/',
            '/api/orders/',
            '/api/menu/',
            '/api/accounts/',
            '/api/payments/',
            '/admin/',
        ]
        
        # Check if path starts with any admin endpoint
        is_admin_endpoint = any(path.startswith(endpoint) for endpoint in admin_endpoints)
        
        # Log write operations (POST, PUT, PATCH, DELETE) and admin GET requests
        should_log = (
            is_admin_endpoint and (
                method in ['POST', 'PUT', 'PATCH', 'DELETE'] or
                (method == 'GET' and 'analytics' in path) or
                (method == 'GET' and 'audit-logs' in path)
            )
        )
        
        return should_log
    
    def _log_request(self, request: HttpRequest, response: HttpResponse) -> None:
        """Create an audit log entry for the request."""
        try:
            audit_data = request._audit_data
            
            # Determine action based on method and path
            action = self._determine_action(request.method, request.path)
            
            # Determine severity
            severity = self._determine_severity(request.method, response.status_code)
            
            # Create description
            description = f"{request.method} {request.path} - Status: {response.status_code}"
            
            # Prepare metadata
            metadata = {
                'status_code': response.status_code,
                'content_type': response.get('Content-Type', ''),
            }
            
            # Add request body for write operations
            if request.method in ['POST', 'PUT', 'PATCH'] and 'request_body' in audit_data:
                try:
                    # Try to parse as JSON for better storage
                    body_data = json.loads(audit_data['request_body'])
                    metadata['request_data'] = body_data
                except (json.JSONDecodeError, ValueError):
                    metadata['request_body'] = audit_data['request_body'][:1000]  # Limit size
            
            # Create audit log entry
            AuditLog.objects.create(
                user=request.user,
                action=action,
                description=description,
                ip_address=audit_data['ip_address'],
                user_agent=audit_data['user_agent'][:500],  # Limit user agent length
                request_path=request.path,
                request_method=request.method,
                severity=severity,
                category='api_request',
                metadata=metadata
            )
            
        except Exception as e:
            # Don't let audit logging break the application
            # In production, you might want to log this error somewhere
            pass
    
    def _determine_action(self, method: str, path: str) -> str:
        """Determine the action type based on method and path."""
        if 'analytics' in path:
            return 'view_analytics'
        elif 'audit-logs' in path:
            return 'view_audit_logs'
        elif method == 'POST':
            return 'create'
        elif method == 'PUT':
            return 'update'
        elif method == 'PATCH':
            return 'partial_update'
        elif method == 'DELETE':
            return 'delete'
        elif method == 'GET':
            return 'view'
        else:
            return 'unknown'
    
    def _determine_severity(self, method: str, status_code: int) -> str:
        """Determine severity based on method and response status."""
        if status_code >= 500:
            return 'critical'
        elif status_code >= 400:
            return 'warning'
        elif method in ['DELETE']:
            return 'high'
        elif method in ['POST', 'PUT', 'PATCH']:
            return 'medium'
        else:
            return 'low'
    
    def _get_client_ip(self, request: HttpRequest) -> str:
        """Extract client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip or 'unknown'