from __future__ import annotations
from rest_framework import serializers
from .models import Table, Reservation

class TableStatusSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    table_number = serializers.CharField()
    capacity = serializers.IntegerField()
    status = serializers.ChoiceField(choices=["available", "reserved", "busy"])
    hold_seconds = serializers.IntegerField(required=False, allow_null=True)
    reservation_id = serializers.IntegerField(required=False, allow_null=True)
    reservation_status = serializers.CharField(required=False, allow_blank=True)

class CreateReservationSerializer(serializers.Serializer):
    table_id = serializers.IntegerField()
    date = serializers.DateField()
    time = serializers.TimeField()
    end_time = serializers.TimeField(required=False)
    party_size = serializers.IntegerField(min_value=1)
    customer_name = serializers.CharField(max_length=200)
    customer_phone = serializers.CharField(max_length=20)
    customer_email = serializers.EmailField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        # Basic capacity check using existing Table model
        try:
            table = Table.objects.get(pk=attrs["table_id"])
        except Table.DoesNotExist:
            raise serializers.ValidationError("Table not found.")
        if attrs["party_size"] > table.capacity:
            raise serializers.ValidationError("Party size exceeds table capacity.")
        return attrs

    def create(self, validated):
        from django.utils import timezone
        from datetime import datetime, timedelta
        request = self.context["request"]
        user = request.user
        table = Table.objects.get(pk=validated["table_id"])
        # Combine date + time; make aware in current timezone
        naive = datetime.combine(validated["date"], validated["time"]).replace(second=0, microsecond=0)
        start = timezone.make_aware(naive, timezone.get_current_timezone()) if timezone.is_naive(naive) else naive
        if validated.get("end_time"):
            naive_end = datetime.combine(validated["date"], validated["end_time"]).replace(second=0, microsecond=0)
            end = timezone.make_aware(naive_end, timezone.get_current_timezone()) if timezone.is_naive(naive_end) else naive_end
            # Robustness: if end <= start, interpret as next-day end
            if end <= start:
                end = end + timedelta(days=1)
        else:
            end = start + timedelta(minutes=90)
        # Sanity: bound maximum duration to 6 hours to avoid accidental 24h bookings
        if (end - start).total_seconds() > 6 * 3600:
            from rest_framework.exceptions import ValidationError
            raise ValidationError("Reservation duration cannot exceed 6 hours.")
        from django.core.exceptions import ValidationError as DjangoValidationError
        try:
            res = Reservation.objects.create(
                location=table.location,
                table=table,
                guest_name=validated["customer_name"],
                guest_phone=validated["customer_phone"],
                party_size=validated["party_size"],
                start_time=start,
                end_time=end,
                note=validated.get("notes", ""),
                created_by=user,
            )
        except DjangoValidationError as e:
            from rest_framework.exceptions import ValidationError as DRFValidationError
            # Normalize to DRF validation error for consistent 400 handling
            payload = getattr(e, 'message_dict', None) or getattr(e, 'messages', None) or str(e)
            raise DRFValidationError(payload)
        return res

class ReservationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reservation
        fields = [
            "id", "location", "table", "guest_name", "guest_phone", "party_size",
            "start_time", "end_time", "reservation_date", "status", "note",
            "deposit_amount", "deposit_paid", "deposit_applied",
            "created_by", "created_at",
        ]
        read_only_fields = ["created_by", "created_at", "reservation_date", "deposit_paid", "deposit_applied"]
