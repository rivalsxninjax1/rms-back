from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    DailySalesViewSet, 
    ShiftReportViewSet,
    OrderAnalyticsViewSet,
    MenuAnalyticsViewSet,
    AuditLogViewSet,
)

app_name = "reports"

router = DefaultRouter()
router.register(r"reports/daily-sales", DailySalesViewSet, basename="daily-sales")
router.register(r"reports/shifts", ShiftReportViewSet, basename="shift-report")
# Core audit logs deprecated; use reports audit logs endpoint below
router.register(r"analytics/orders", OrderAnalyticsViewSet, basename="order-analytics")
router.register(r"analytics/menu", MenuAnalyticsViewSet, basename="menu-analytics")
router.register(r"audit-logs", AuditLogViewSet, basename="audit-logs")

urlpatterns = [
    path("", include(router.urls)),
]
