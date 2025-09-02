# core/api_urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .api_views import (
    OrganizationViewSet, LocationViewSet, ServiceTypeViewSet, TableViewSet,
    ReservationViewSet, AdminTableViewSet, AdminReservationViewSet
)

# Create router for public API endpoints
router = DefaultRouter()
router.register(r'organizations', OrganizationViewSet, basename='organization')
router.register(r'locations', LocationViewSet, basename='location')
router.register(r'service-types', ServiceTypeViewSet, basename='servicetype')
router.register(r'tables', TableViewSet, basename='table')
router.register(r'reservations', ReservationViewSet, basename='reservation')

# Create router for admin API endpoints
admin_router = DefaultRouter()
admin_router.register(r'tables', AdminTableViewSet, basename='admin-table')
admin_router.register(r'reservations', AdminReservationViewSet, basename='admin-reservation')

urlpatterns = [
    path('core/', include(router.urls)),
    path('core/admin/', include(admin_router.urls)),
]

# URL patterns will be:
# Public API:
# /core/api/organizations/ - List organizations
# /core/api/organizations/{id}/ - Retrieve specific organization
# /core/api/locations/ - List locations
# /core/api/locations/{id}/ - Retrieve specific location
# /core/api/service-types/ - List service types
# /core/api/service-types/{id}/ - Retrieve specific service type
# /core/api/service-types/{id}/availability/ - Check availability for date
# /core/api/tables/ - List tables (with filters)
# /core/api/tables/{id}/ - Retrieve specific table
# /core/api/tables/{id}/availability/ - Check table availability
# /core/api/reservations/ - List/Create reservations
# /core/api/reservations/{id}/ - Retrieve/Update/Delete specific reservation
# /core/api/reservations/{id}/cancel/ - Cancel reservation
# /core/api/reservations/{id}/modify/ - Modify reservation
# /core/api/reservations/upcoming/ - Get upcoming reservations
# /core/api/reservations/history/ - Get reservation history
#
# Admin API:
# /core/api/admin/tables/ - Full CRUD for tables
# /core/api/admin/tables/{id}/toggle_active/ - Toggle table active status
# /core/api/admin/reservations/ - Full CRUD for reservations
# /core/api/admin/reservations/{id}/mark_seated/ - Mark as seated
# /core/api/admin/reservations/{id}/mark_completed/ - Mark as completed
# /core/api/admin/reservations/{id}/mark_no_show/ - Mark as no show