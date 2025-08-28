from __future__ import annotations

from rest_framework import serializers

from .models import DailySales, ShiftReport


class DailySalesSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailySales
        fields = ["id", "date", "total_orders", "subtotal_cents", "tip_cents", "discount_cents", "total_cents", "created_at"]


class ShiftReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShiftReport
        fields = ["id", "date", "shift", "staff", "orders_count", "total_cents", "created_at"]
