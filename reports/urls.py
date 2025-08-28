from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DailySalesViewSet, ShiftReportViewSet

app_name = "reports"

router = DefaultRouter()
router.register(r"reports/daily-sales", DailySalesViewSet, basename="daily-sales")
router.register(r"reports/shifts", ShiftReportViewSet, basename="shift-report")

urlpatterns = [
    path("", include(router.urls)),
]
