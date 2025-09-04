from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import OrganizationViewSet, LocationViewSet, health_check
from . import test_views

app_name = "core"

router = DefaultRouter()
router.register('organizations', OrganizationViewSet)
router.register('locations', LocationViewSet)

# Health check endpoint
health_urlpatterns = [
    path('health/', health_check, name='health_check'),
]

# Test URLs for error handling middleware
test_urlpatterns = [
    path('test/404/', test_views.test_404_error, name='test_404'),
    path('test/403/', test_views.test_403_error, name='test_403'),
    path('test/400/', test_views.test_400_error, name='test_400'),
    path('test/500/', test_views.test_500_error, name='test_500'),
    path('test/db-error/', test_views.test_database_error, name='test_db_error'),
    path('test/json-error/', test_views.test_json_error, name='test_json_error'),
    path('test/success/', test_views.test_success, name='test_success'),
]

urlpatterns = router.urls + health_urlpatterns + test_urlpatterns
