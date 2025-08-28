from __future__ import annotations

from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAdminUser

from .models import DailySales, ShiftReport
from .serializers import DailySalesSerializer, ShiftReportSerializer


class DailySalesViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    Read-only API for daily sales aggregates (admin-only).
    """
    queryset = DailySales.objects.all()
    serializer_class = DailySalesSerializer
    permission_classes = [IsAdminUser]
    filterset_fields = ["date"]
    ordering = ["-date", "-id"]


class ShiftReportViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    Read-only API for shift reports (admin-only).
    """
    queryset = ShiftReport.objects.all()
    serializer_class = ShiftReportSerializer
    permission_classes = [IsAdminUser]
    filterset_fields = ["date", "shift"]
    ordering = ["-date", "shift", "-id"]
