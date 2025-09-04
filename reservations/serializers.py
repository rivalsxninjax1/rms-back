from __future__ import annotations

from typing import Any

from django.utils import timezone
from rest_framework import serializers

from .models import Table, Reservation


class TableSerializer(serializers.ModelSerializer):
    class Meta:
        model = Table
        fields = ["id", "location", "table_number", "capacity", "is_active", "created_at"]


class ReservationSerializer(serializers.ModelSerializer):
    """
    Serializer aligned with the (fixed) Reservation model.
    - Accepts start_time / end_time as ISO strings.
    - Keeps reservation_date in sync in the model.save().
    """
    class Meta:
        model = Reservation
        fields = [
            "id",
            "location",
            "table",
            "created_by",
            "guest_name",
            "guest_phone",
            "party_size",
            "start_time",
            "end_time",
            "reservation_date",
            "note",
            "status",
            "deposit_amount",
            "deposit_paid",
            "deposit_applied",
            "created_at",
        ]
        read_only_fields = ["reservation_date", "created_at", "deposit_paid", "deposit_applied"]

    def to_representation(self, instance: Reservation) -> dict[str, Any]:
        data = super().to_representation(instance)
        # Normalize datetimes to ISO
        for f in ("start_time", "end_time"):
            val = getattr(instance, f, None)
            if val is not None:
                try:
                    data[f] = timezone.localtime(val).isoformat()
                except Exception:
                    data[f] = val.isoformat()
        return data


class WalkInReservationSerializer(serializers.Serializer):
    """
    Input serializer for walk-in reservations.
    """
    table_id = serializers.IntegerField(min_value=1)
    minutes = serializers.IntegerField(required=False, min_value=15, max_value=360, default=90)
    guest_name = serializers.CharField(required=False, allow_blank=True, max_length=120)
    party_size = serializers.IntegerField(required=False, min_value=1, max_value=50, default=2)
    phone = serializers.CharField(required=False, allow_blank=True, max_length=40)

    def validate_table_id(self, value: int) -> int:
        try:
            Table.objects.get(pk=value)
        except Table.DoesNotExist:
            raise serializers.ValidationError("Table not found.")
        return value

    def validate(self, attrs):
        # Ensure table is active and capacity meets party_size
        table = Table.objects.get(pk=attrs["table_id"])  # safe after validate_table_id
        if not getattr(table, "is_active", True):
            raise serializers.ValidationError({"table_id": "Table is not active."})
        party = int(attrs.get("party_size") or 2)
        if getattr(table, "capacity", party) < party:
            raise serializers.ValidationError({"party_size": "Party size exceeds table capacity."})
        attrs["_table_obj"] = table
        attrs["_location_obj"] = getattr(table, "location", None)
        return attrs
