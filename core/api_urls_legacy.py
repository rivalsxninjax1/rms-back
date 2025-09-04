"""
Backward-compatible Core API URLs mounted at /core/api/.

These mirror the routers defined in core.api_urls but without the extra
"core/" prefix so that older frontend code calling /core/api/* continues
to work while the new canonical mount remains /api/core/*.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .api_views import (
    OrganizationViewSet, LocationViewSet, ServiceTypeViewSet, TableViewSet,
    ReservationViewSet, AdminTableViewSet, AdminReservationViewSet
)


# Public API endpoints (no additional prefix; mounted at /core/api/)
router = DefaultRouter()
router.register(r'organizations', OrganizationViewSet, basename='legacy-organization')
router.register(r'locations', LocationViewSet, basename='legacy-location')
router.register(r'service-types', ServiceTypeViewSet, basename='legacy-servicetype')
router.register(r'tables', TableViewSet, basename='legacy-table')
router.register(r'reservations', ReservationViewSet, basename='legacy-reservation')

# Admin API endpoints under /core/api/admin/
admin_router = DefaultRouter()
admin_router.register(r'tables', AdminTableViewSet, basename='legacy-admin-table')
admin_router.register(r'reservations', AdminReservationViewSet, basename='legacy-admin-reservation')

urlpatterns = [
    path('', include(router.urls)),
    path('admin/', include(admin_router.urls)),
]

