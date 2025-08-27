# rms_backend/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),

    # Coupons
    path("coupons/", include("coupons.urls")),

    # Normal session endpoints for login/register/logout/whoami
    path("accounts/", include(("accounts.urls", "accounts"), namespace="accounts_session")),

    # APIs
    path("api/", include(("orders.urls", "orders"), namespace="orders_api")),
    path("api/payments/", include(("payments.urls", "payments"), namespace="payments")),
    path("api/menu/", include(("menu.urls", "menu"), namespace="menu_api")),
    path("api/reservations/", include(("reservations.urls", "reservations"), namespace="reservations_api")),

    # Portal routes
    path("reserve/", include("reservations.urls_portal", namespace="reservations_portal")),

    # Loyalty preview (NEW)
    path("loyalty/", include(("loyality.urls", "loyality"), namespace="loyalty")),

    # Storefront pages
    path("", include(("storefront.urls", "storefront"), namespace="storefront")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Error handlers
handler400 = "storefront.views.http_400"
handler403 = "storefront.views.http_403"
handler404 = "storefront.views.http_404"
handler500 = "storefront.views.http_500"
