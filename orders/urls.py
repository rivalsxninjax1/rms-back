from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api_views import CartViewSet, OrderViewSet, OrderItemViewSet
from . import views

# Create router and register viewsets
router = DefaultRouter()
router.register(r'carts', CartViewSet, basename='cart')
router.register(r'orders', OrderViewSet, basename='order')
router.register(r'order-items', OrderItemViewSet, basename='orderitem')

# URL patterns
urlpatterns = [
    path('', include(router.urls)),
    # Third-party delivery webhooks (Uber Eats / DoorDash)
    path('webhooks/ubereats/', views.ubereats_webhook, name='ubereats_webhook'),
    path('webhooks/doordash/', views.doordash_webhook, name='doordash_webhook'),
]

# Additional custom endpoints can be added here if needed
# urlpatterns += [
#     path('api/custom-endpoint/', custom_view, name='custom-endpoint'),
# ]
