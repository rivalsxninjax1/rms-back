from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .api_views import LoyaltyProfileViewSet, LoyaltyRankViewSet, LoyaltyLedgerViewSet

router = DefaultRouter()
router.register(r'loyalty/ranks', LoyaltyRankViewSet, basename='loyalty-rank')
router.register(r'loyalty/profiles', LoyaltyProfileViewSet, basename='loyalty-profile')
router.register(r'loyalty/ledger', LoyaltyLedgerViewSet, basename='loyalty-ledger')

urlpatterns = [
    path('', include(router.urls)),
]

