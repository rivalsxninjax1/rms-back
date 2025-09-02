from rest_framework import viewsets
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import redirect, render
from django.http import HttpResponse
from django.conf import settings
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
