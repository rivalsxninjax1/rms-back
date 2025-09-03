# rms_backend/urls.py
from __future__ import annotations

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from core.views import storefront_redirect, storefront_view, cart_view
urlpatterns = [
    # Django-rendered Storefront at root
    path("", include(("storefront.urls", "storefront"), namespace="storefront")),
    
    # Legacy React pages (if needed)
    path("app/", storefront_view, name="storefront_react"),
    
    # Legacy redirect for old storefront URL
    path("storefront/", storefront_view, name="storefront_legacy"),
    path("redirect/", storefront_redirect, name="storefront_redirect"),
    
    path("admin/", admin.site.urls),
    
    # API Documentation
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),

    # Accounts (session JSON for modal; also JWT optional endpoints are inside)
    # FIX: use the "accounts" namespace to match includes elsewhere in the project
    path("accounts/", include(("accounts.urls", "accounts"), namespace="accounts")),

    # Coupons (kept on its own prefix to preserve existing links)
    path("coupons/", include(("coupons.urls", "coupons"), namespace="coupons")),

    # (shop/ mount removed; storefront now at root)

    # Payments (Stripe checkout + webhook)
    path("payments/", include(("payments.urls", "payments"), namespace="payments")),
    # Reservation portal (interactive booking UI)
    path("reserve/", include(("reservations.urls_portal", "reservations_portal"), namespace="reservations_portal")),

    # ---- Comprehensive REST APIs ----
    # New comprehensive DRF APIs with full CRUD operations
    path("api/", include(("core.api_urls", "core_api"), namespace="core_api")),
    path("api/", include(("menu.api_urls", "menu_api"), namespace="menu_api")),
    path("api/", include(("orders.api_urls", "orders_api"), namespace="orders_api")),
    path("api/", include(("reports.urls", "reports"), namespace="reports")),
    path("api/", include(("reservations.urls", "reservations"), namespace="reservations")),
    path("api/", include(("loyality.urls", "loyality"), namespace="loyality")),
    path("api/payments/", include(("payments.urls", "payments_api"), namespace="payments_api"))
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Error handlers (served by storefront)
# Error handlers (storefront is React app, not Django app)
# handler400 = "storefront.views.http_400"
# handler403 = "storefront.views.http_403"
# handler404 = "storefront.views.http_404"
# handler500 = "storefront.views.http_500"
