import uuid
import logging
from django.utils.deprecation import MiddlewareMixin
from threading import local

# Thread-local storage for request ID
_thread_locals = local()

class RequestIDMiddleware(MiddlewareMixin):
    """
    Middleware that adds a unique request ID to each request and makes it available
    to logging throughout the request lifecycle.
    """
    
    def process_request(self, request):
        """
        Generate a unique request ID and store it in thread-local storage.
        """
        # Generate a unique request ID
        request_id = str(uuid.uuid4())
        
        # Store in request object
        request.request_id = request_id
        
        # Store in thread-local storage for logging
        _thread_locals.request_id = request_id
        
        # Add to response headers (optional, for debugging)
        return None
    
    def process_response(self, request, response):
        """
        Add request ID to response headers and clean up thread-local storage.
        """
        # Add request ID to response headers
        if hasattr(request, 'request_id'):
            response['X-Request-ID'] = request.request_id
        
        # Clean up thread-local storage
        if hasattr(_thread_locals, 'request_id'):
            delattr(_thread_locals, 'request_id')
        
        return response
    
    def process_exception(self, request, exception):
        """
        Ensure thread-local storage is cleaned up even if an exception occurs.
        """
        if hasattr(_thread_locals, 'request_id'):
            delattr(_thread_locals, 'request_id')
        return None


def get_request_id():
    """
    Utility function to get the current request ID from thread-local storage.
    Returns None if no request ID is available.
    """
    return getattr(_thread_locals, 'request_id', None)


class RequestIDFilter(logging.Filter):
    """
    Logging filter that adds request ID to log records.
    """
    
    def filter(self, record):
        record.request_id = get_request_id() or 'no-request-id'
        return True