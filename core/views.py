from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import redirect, render
from django.http import HttpResponse
from django.conf import settings
from django.db import connection
from django.core.cache import cache
import logging
import time
from .models import Organization, Location
from .serializers import OrganizationSerializer, LocationSerializer


def storefront_redirect(request):
    """Redirect root URL to the React storefront."""
    storefront_url = getattr(settings, 'STOREFRONT_URL', 'http://localhost:3000')
    return redirect(storefront_url)


def storefront_view(request):
    """Serve the HTML/CSS/JS frontend."""
    return render(request, 'index.html')


def cart_view(request):
    """Serve the cart page."""
    return render(request, 'cart.html')


# ---- Favicon and Apple Touch Icons (prevent 404s) ----
_PNG_DOT = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\x0cIDAT\x08\x99c``\xf8\x0f\x00\x01\x01\x01\x00\x18\xdd\x8d\x1a\x00\x00\x00\x00IEND\xaeB`\x82"
)

def _png_response(data: bytes) -> HttpResponse:
    resp = HttpResponse(data, content_type="image/png")
    resp["Cache-Control"] = "public, max-age=86400"
    return resp

def favicon(request):
    return _png_response(_PNG_DOT)

def apple_touch_icon(request):
    return _png_response(_PNG_DOT)

def apple_touch_icon_precomposed(request):
    return _png_response(_PNG_DOT)




class OrganizationViewSet(viewsets.ModelViewSet):
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['name']

class LocationViewSet(viewsets.ModelViewSet):
    queryset = Location.objects.select_related('organization').all()
    serializer_class = LocationSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['organization', 'is_active']


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """
    Health check endpoint that verifies database, cache, and broker connectivity.
    Returns 200 if all services are healthy, 503 if any service is down.
    """
    logger = logging.getLogger(__name__)
    health_status = {
        'status': 'healthy',
        'timestamp': time.time(),
        'services': {}
    }
    
    overall_healthy = True
    
    # Database check
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
        health_status['services']['database'] = {
            'status': 'healthy',
            'response_time_ms': 0
        }
    except Exception as e:
        logger.error(f'Database health check failed: {e}')
        health_status['services']['database'] = {
            'status': 'unhealthy',
            'error': str(e)
        }
        overall_healthy = False
    
    # Cache check
    try:
        start_time = time.time()
        cache_key = 'health_check_test'
        cache.set(cache_key, 'test_value', 30)
        cached_value = cache.get(cache_key)
        cache.delete(cache_key)
        response_time = (time.time() - start_time) * 1000
        
        if cached_value == 'test_value':
            health_status['services']['cache'] = {
                'status': 'healthy',
                'response_time_ms': round(response_time, 2)
            }
        else:
            raise Exception('Cache value mismatch')
    except Exception as e:
        logger.error(f'Cache health check failed: {e}')
        health_status['services']['cache'] = {
            'status': 'unhealthy',
            'error': str(e)
        }
        overall_healthy = False
    
    # Broker check (Celery/Redis)
    try:
        from celery import current_app
        from kombu import Connection
        
        # Get broker URL from Celery settings
        broker_url = current_app.conf.broker_url
        
        start_time = time.time()
        with Connection(broker_url) as conn:
            conn.connect()
            response_time = (time.time() - start_time) * 1000
            
        health_status['services']['broker'] = {
            'status': 'healthy',
            'response_time_ms': round(response_time, 2)
        }
    except ImportError:
        # Celery not configured
        health_status['services']['broker'] = {
            'status': 'not_configured',
            'message': 'Celery not configured'
        }
    except Exception as e:
        logger.error(f'Broker health check failed: {e}')
        health_status['services']['broker'] = {
            'status': 'unhealthy',
            'error': str(e)
        }
        overall_healthy = False
    
    # Set overall status
    if not overall_healthy:
        health_status['status'] = 'unhealthy'
    
    # Return appropriate HTTP status code
    status_code = 200 if overall_healthy else 503
    return Response(health_status, status=status_code)
