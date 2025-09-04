from __future__ import annotations

from rest_framework import serializers
from .models import Coupon


class CouponSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coupon
        fields = [
            'id', 'code', 'name', 'description', 'phrase',
            'discount_type', 'percent', 'fixed_amount',
            'minimum_order_amount', 'maximum_discount_amount',
            'active', 'valid_from', 'valid_to',
            'max_uses', 'max_uses_per_customer', 'times_used',
            'customer_type', 'first_order_only',
            'stackable_with_other_coupons', 'stackable_with_loyalty',
            'buy_quantity', 'get_quantity',
            'total_discount_given', 'created_by', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'times_used', 'total_discount_given', 'created_by', 'created_at', 'updated_at']

