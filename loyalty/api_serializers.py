from __future__ import annotations

from rest_framework import serializers
from loyalty.models import LoyaltyProfile, LoyaltyRank, LoyaltyPointsLedger


class LoyaltyRankSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoyaltyRank
        fields = [
            'id', 'code', 'name', 'tip_cents', 'earn_points_per_currency', 'burn_cents_per_point', 'is_active', 'sort_order'
        ]


class LoyaltyPointsLedgerSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoyaltyPointsLedger
        fields = ['id', 'profile', 'delta', 'type', 'reason', 'reference', 'created_by', 'created_at']
        read_only_fields = ['id', 'created_by', 'created_at']


class LoyaltyProfileSerializer(serializers.ModelSerializer):
    rank = LoyaltyRankSerializer(read_only=True)
    rank_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = LoyaltyProfile
        fields = ['id', 'user', 'rank', 'rank_id', 'points', 'notes']
        read_only_fields = ['id', 'user']

    def update(self, instance, validated_data):
        rid = validated_data.pop('rank_id', None)
        for k, v in validated_data.items():
            setattr(instance, k, v)
        if rid is not None:
            instance.rank_id = rid or None
        instance.save()
        return instance
