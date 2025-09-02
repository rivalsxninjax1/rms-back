from datetime import datetime, timedelta
from decimal import Decimal

from django.utils import timezone
from django.db import transaction
from rest_framework import serializers

from .models import Organization, Location, Table, ServiceType, Reservation


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = '__all__'


class LocationSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    
    class Meta:
        model = Location
        fields = '__all__'


class ServiceTypeSerializer(serializers.ModelSerializer):
    """Serializer for ServiceType with validation."""
    
    class Meta:
        model = ServiceType
        fields = [
            'id', 'name', 'code', 'description', 'base_fee', 
            'requires_table', 'allows_reservations', 'max_advance_days',
            'min_advance_minutes', 'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def validate_code(self, value):
        """Validate service type code format."""
        if not value.isupper():
            raise serializers.ValidationError("Service type code must be uppercase.")
        if len(value) < 2 or len(value) > 10:
            raise serializers.ValidationError("Service type code must be 2-10 characters.")
        return value
    
    def validate_base_fee(self, value):
        """Validate base fee is non-negative."""
        if value < Decimal('0.00'):
            raise serializers.ValidationError("Base fee cannot be negative.")
        return value
    
    def validate(self, data):
        """Validate service type constraints."""
        allows_reservations = data.get('allows_reservations', False)
        max_advance_days = data.get('max_advance_days')
        min_advance_minutes = data.get('min_advance_minutes')
        
        if allows_reservations:
            if max_advance_days is None or max_advance_days <= 0:
                raise serializers.ValidationError(
                    "max_advance_days must be positive when reservations are allowed."
                )
            if min_advance_minutes is None or min_advance_minutes < 0:
                raise serializers.ValidationError(
                    "min_advance_minutes must be non-negative when reservations are allowed."
                )
        
        return data


class TableSerializer(serializers.ModelSerializer):
    """Serializer for Table with location details."""
    location_name = serializers.CharField(source='location.name', read_only=True)
    
    class Meta:
        model = Table
        fields = [
            'id', 'location', 'location_name', 'table_number', 
            'capacity', 'table_type', 'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def validate_table_number(self, value):
        """Validate table number format."""
        if not value or len(value.strip()) == 0:
            raise serializers.ValidationError("Table number cannot be empty.")
        return value.strip()
    
    def validate_capacity(self, value):
        """Validate table capacity."""
        if value <= 0:
            raise serializers.ValidationError("Table capacity must be positive.")
        if value > 50:
            raise serializers.ValidationError("Table capacity cannot exceed 50.")
        return value


class ReservationCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating reservations with validation."""
    
    class Meta:
        model = Reservation
        fields = [
            'user', 'guest_name', 'guest_phone', 'guest_email',
            'table', 'service_type', 'party_size', 'reservation_date',
            'reservation_time', 'duration_minutes', 'special_requests'
        ]
    
    def validate_party_size(self, value):
        """Validate party size."""
        if value <= 0:
            raise serializers.ValidationError("Party size must be positive.")
        if value > 50:
            raise serializers.ValidationError("Party size cannot exceed 50.")
        return value
    
    def validate_duration_minutes(self, value):
        """Validate reservation duration."""
        if value <= 0:
            raise serializers.ValidationError("Duration must be positive.")
        if value > 480:  # 8 hours
            raise serializers.ValidationError("Duration cannot exceed 8 hours.")
        return value
    
    def validate(self, data):
        """Validate reservation constraints."""
        table = data.get('table')
        service_type = data.get('service_type')
        party_size = data.get('party_size')
        reservation_date = data.get('reservation_date')
        reservation_time = data.get('reservation_time')
        
        # Validate service type allows reservations
        if service_type and not service_type.allows_reservations:
            raise serializers.ValidationError(
                f"Service type '{service_type.name}' does not allow reservations."
            )
        
        # Validate table capacity
        if table and party_size and party_size > table.capacity:
            raise serializers.ValidationError(
                f"Party size ({party_size}) exceeds table capacity ({table.capacity})."
            )
        
        # Validate reservation timing
        if reservation_date and reservation_time and service_type:
            reservation_datetime = timezone.make_aware(
                datetime.combine(reservation_date, reservation_time)
            )
            now = timezone.now()
            
            # Check minimum advance time
            min_advance = timedelta(minutes=service_type.min_advance_minutes)
            if reservation_datetime < now + min_advance:
                raise serializers.ValidationError(
                    f"Reservation must be at least {service_type.min_advance_minutes} minutes in advance."
                )
            
            # Check maximum advance time
            max_advance = timedelta(days=service_type.max_advance_days)
            if reservation_datetime > now + max_advance:
                raise serializers.ValidationError(
                    f"Reservation cannot be more than {service_type.max_advance_days} days in advance."
                )
        
        return data
    
    @transaction.atomic
    def create(self, validated_data):
        """Create reservation with availability check."""
        table = validated_data['table']
        reservation_date = validated_data['reservation_date']
        reservation_time = validated_data['reservation_time']
        duration_minutes = validated_data['duration_minutes']
        
        # Check availability
        reservation_datetime = timezone.make_aware(
            datetime.combine(reservation_date, reservation_time)
        )
        
        if not Reservation.check_availability(
            table, reservation_datetime, duration_minutes
        ):
            raise serializers.ValidationError(
                "Table is not available at the requested time."
            )
        
        # Create reservation
        reservation = Reservation.objects.create(**validated_data)
        return reservation


class ReservationSerializer(serializers.ModelSerializer):
    """Comprehensive serializer for Reservation with related data."""
    table_number = serializers.CharField(source='table.table_number', read_only=True)
    service_type_name = serializers.CharField(source='service_type.name', read_only=True)
    end_time = serializers.SerializerMethodField()
    
    class Meta:
        model = Reservation
        fields = [
            'id', 'reservation_uuid', 'confirmation_number', 'user',
            'guest_name', 'guest_phone', 'guest_email', 'table', 'table_number',
            'service_type', 'service_type_name', 'party_size', 'reservation_date',
            'reservation_time', 'end_time', 'duration_minutes', 'status',
            'special_requests', 'internal_notes', 'deposit_required',
            'deposit_amount', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'reservation_uuid', 'confirmation_number', 'end_time',
            'created_at', 'updated_at'
        ]
    
    def get_end_time(self, obj):
        """Calculate reservation end time."""
        return obj.get_end_time()


class ReservationListSerializer(serializers.ModelSerializer):
    """Compact serializer for listing reservations."""
    table_number = serializers.CharField(source='table.table_number', read_only=True)
    service_type_name = serializers.CharField(source='service_type.name', read_only=True)
    
    class Meta:
        model = Reservation
        fields = [
            'id', 'confirmation_number', 'guest_name', 'party_size',
            'table_number', 'service_type_name', 'reservation_date',
            'reservation_time', 'status', 'created_at'
        ]