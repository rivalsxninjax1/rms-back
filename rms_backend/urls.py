# rms_backend/urls.py
from __future__ import annotations

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path, re_path
from django.views.generic import TemplateView
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from core.views import storefront_redirect, storefront_view, cart_view

class AdminSPAView(TemplateView):
    template_name = "rms_admin_spa/index.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context
urlpatterns = [
    # Django-rendered Storefront at root
    path("", include(("storefront.urls", "storefront"), namespace="storefront")),
    
    # Legacy React pages (if needed)
    path("app/", storefront_view, name="storefront_react"),
    
    # Legacy redirect for old storefront URL
    path("storefront/", storefront_view, name="storefront_legacy"),
    path("redirect/", storefront_redirect, name="storefront_redirect"),
    
    # Auth endpoints for login/logout
    path("api/auth/", include("rest_framework.urls")),
    path('accounts/login/', auth_views.LoginView.as_view(), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    
    # Django default admin interface
    path("admin/", admin.site.urls),
    
    # React admin panel at /rms-admin/
    path("rms-admin/", AdminSPAView.as_view(), name="rms_admin_spa"),
    re_path(r"^rms-admin/(?P<path>.*)$", AdminSPAView.as_view(), name="rms_admin_spa_catchall"),
    
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
    path("api/", include(("coupons.api_urls", "coupons_api"), namespace="coupons_api")),
    path("api/", include(("loyalty.api_urls", "loyalty_api"), namespace="loyalty_api")),
    # Backward-compat: both spellings available during transition
    path("api/", include(("loyalty.urls", "loyalty"), namespace="loyalty")),
    path("api/", include(("loyality.urls", "loyality"), namespace="loyality")),
    path("api/payments/", include(("payments.urls", "payments_api"), namespace="payments_api")),

    # Backward compatibility for older frontend expecting /core/api/*
    path("core/api/", include(("core.api_urls_legacy", "core_api_legacy"), namespace="core_api_legacy")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Error handlers (served by storefront)
# Error handlers (storefront is React app, not Django app)
# handler400 = "storefront.views.http_400"
# handler403 = "storefront.views.http_403"
# handler404 = "storefront.views.http_404"
# handler500 = "storefront.views.http_500"
