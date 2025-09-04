from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    DailySalesViewSet, 
    ShiftReportViewSet,
    OrderAnalyticsViewSet,
    MenuAnalyticsViewSet,
    AuditLogViewSet,
    CoreAuditLogViewSet
)

app_name = "reports"

router = DefaultRouter()
router.register(r"reports/daily-sales", DailySalesViewSet, basename="daily-sales")
router.register(r"reports/shifts", ShiftReportViewSet, basename="shift-report")
router.register(r"reports/audit", CoreAuditLogViewSet, basename="core-audit")
router.register(r"analytics/orders", OrderAnalyticsViewSet, basename="order-analytics")
router.register(r"analytics/menu", MenuAnalyticsViewSet, basename="menu-analytics")
router.register(r"audit-logs", AuditLogViewSet, basename="audit-logs")

urlpatterns = [
    path("", include(router.urls)),
]
