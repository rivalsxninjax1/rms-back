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
            "created_at",
        ]
        read_only_fields = ["reservation_date", "created_at"]

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
