# rms_backend/urls.py
from __future__ import annotations

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

urlpatterns = [
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

    # Public storefront pages
    path("", include(("storefront.urls", "storefront"), namespace="storefront")),

    # Payments (Stripe checkout + webhook)
    path("payments/", include(("payments.urls", "payments"), namespace="payments")),

    # ---- APIs ----
    # Menu, Reports, Reservations, Loyalty — all under /api/
    path("api/", include(("menu.urls", "menu"), namespace="menu")),
    path("api/", include(("reports.urls", "reports"), namespace="reports")),
    path("api/", include(("reservations.urls", "reservations"), namespace="reservations")),
    path("api/", include(("loyality.urls", "loyality"), namespace="loyality")),

    # Orders API — expose under /api/ (new) and /api/orders/ (compat) so legacy JS
    # that calls /api/orders/cart/ keeps working.
    path("api/", include(("orders.urls", "orders"), namespace="orders")),
    path("api/orders/", include(("orders.urls", "orders_compat"), namespace="orders_compat")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Error handlers (served by storefront)
handler400 = "storefront.views.http_400"
handler403 = "storefront.views.http_403"
handler404 = "storefront.views.http_404"
handler500 = "storefront.views.http_500"
