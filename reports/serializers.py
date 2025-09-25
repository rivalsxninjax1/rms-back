from __future__ import annotations

from rest_framework import serializers

from .models import DailySales, ShiftReport, AuditLog


class DailySalesSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailySales
        fields = ["id", "date", "total_orders", "subtotal_cents", "tip_cents", "discount_cents", "total_cents", "created_at"]


class ShiftReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShiftReport
        fields = [
            "id", "date", "shift", "staff",
            "orders_count", "total_cents",
            "opened_at", "closed_at",
            "cash_open_cents", "cash_close_cents", "cash_sales_cents", "over_short_cents",
            "notes",
            "created_at"
        ]


class AuditLogSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source='user.username', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    content_type_name = serializers.CharField(source='content_type.model', read_only=True)
    
    class Meta:
        model = AuditLog
        fields = [
            'id', 'user', 'user_username', 'user_email', 'action', 'description',
            'content_type', 'content_type_name', 'object_id', 'object_repr',
            'model_name', 'changes', 'ip_address', 'user_agent', 'request_path',
            'request_method', 'severity', 'category', 'metadata', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


# Core audit logs have been deprecated; use AuditLogSerializer above.
