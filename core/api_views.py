# core/api_views.py
from datetime import datetime, timedelta
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny

from .models import Organization, Location, ServiceType, Table, Reservation
from .serializers import (
    OrganizationSerializer, LocationSerializer,
    ServiceTypeSerializer, TableSerializer,
    ReservationSerializer, ReservationListSerializer, ReservationCreateSerializer
)


class OrganizationViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for Organization with read-only operations."""
    serializer_class = OrganizationSerializer
    permission_classes = [AllowAny]
    queryset = Organization.objects.all()


class LocationViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for Location with read-only operations."""
    serializer_class = LocationSerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        """Return active locations."""
        return Location.objects.filter(
            is_active=True
        ).select_related('organization')


class ServiceTypeViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for ServiceType with read-only operations."""
    serializer_class = ServiceTypeSerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        """Return active service types."""
        return ServiceType.objects.filter(
            is_active=True
        ).order_by('sort_order', 'name')
    
    @action(detail=True, methods=['get'])
    def availability(self, request, pk=None):
        """Check availability for a service type on a specific date."""
        service_type = self.get_object()
        date_str = request.query_params.get('date')
        
        if not date_str:
            return Response(
                {'error': 'Date parameter is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            check_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response(
                {'error': 'Invalid date format. Use YYYY-MM-DD'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if reservations are allowed for this service type
        if not service_type.allows_reservations:
            return Response({
                'available': False,
                'message': 'Reservations not allowed for this service type'
            })
        
        # Get available time slots (simplified logic)
        available_slots = []
        start_time = datetime.combine(check_date, service_type.start_time or datetime.min.time())
        end_time = datetime.combine(check_date, service_type.end_time or datetime.max.time())
        
        # Generate 30-minute slots
        current_time = start_time
        while current_time < end_time:
            available_slots.append(current_time.strftime('%H:%M'))
            current_time += timedelta(minutes=30)
        
        return Response({
            'available': True,
            'service_type': service_type.name,
            'date': date_str,
            'available_slots': available_slots
        })


class TableViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for Table with read-only operations."""
    serializer_class = TableSerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        """Return active tables."""
        queryset = Table.objects.filter(
            is_active=True
        ).select_related('location').order_by('table_number')
        
        # Filter by capacity if provided
        min_capacity = self.request.query_params.get('min_capacity')
        if min_capacity:
            try:
                queryset = queryset.filter(capacity__gte=int(min_capacity))
            except ValueError:
                pass
        
        return queryset
    
    @action(detail=True, methods=['get'])
    def availability(self, request, pk=None):
        """Check table availability for a specific date and time."""
        table = self.get_object()
        date_str = request.query_params.get('date')
        time_str = request.query_params.get('time')
        duration = request.query_params.get('duration', 120)  # Default 2 hours
        
        if not date_str or not time_str:
            return Response(
                {'error': 'Date and time parameters are required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            check_datetime = datetime.strptime(f"{date_str} {time_str}", '%Y-%m-%d %H:%M')
            check_datetime = timezone.make_aware(check_datetime)
            duration_minutes = int(duration)
        except ValueError:
            return Response(
                {'error': 'Invalid date/time format or duration'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check for conflicting reservations
        end_datetime = check_datetime + timedelta(minutes=duration_minutes)
        conflicting_reservations = Reservation.objects.filter(
            table=table,
            status__in=['confirmed', 'seated'],
            reservation_time__lt=end_datetime,
            end_time__gt=check_datetime
        )
        
        is_available = not conflicting_reservations.exists()
        
        return Response({
            'available': is_available,
            'table_number': table.table_number,
            'capacity': table.capacity,
            'requested_time': check_datetime.isoformat(),
            'duration_minutes': duration_minutes,
            'conflicts': conflicting_reservations.count() if not is_available else 0
        })


class ReservationViewSet(viewsets.ModelViewSet):
    """ViewSet for Reservation management."""
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'create':
            return ReservationCreateSerializer
        elif self.action == 'list':
            return ReservationListSerializer
        return ReservationSerializer
    
    def get_queryset(self):
        """Filter reservations by user."""
        if self.request.user.is_authenticated:
            queryset = self.request.user.core_reservations.filter(
            ).select_related(
                'service_type', 'table'
            ).order_by('-reservation_time')
            
            # Filter by status if provided
            status_filter = self.request.query_params.get('status')
            if status_filter:
                queryset = queryset.filter(status=status_filter)
            
            # Filter by date range
            start_date = self.request.query_params.get('start_date')
            end_date = self.request.query_params.get('end_date')
            
            if start_date:
                try:
                    start_datetime = datetime.strptime(start_date, '%Y-%m-%d')
                    start_datetime = timezone.make_aware(start_datetime)
                    queryset = queryset.filter(reservation_time__gte=start_datetime)
                except ValueError:
                    pass
            
            if end_date:
                try:
                    end_datetime = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
                    end_datetime = timezone.make_aware(end_datetime)
                    queryset = queryset.filter(reservation_time__lt=end_datetime)
                except ValueError:
                    pass
            
            return queryset
        return Reservation.objects.none()
    
    def perform_create(self, serializer):
        """Set user when creating reservation."""
        serializer.save(user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel a reservation."""
        reservation = self.get_object()
        
        if reservation.status in ['cancelled', 'completed', 'no_show']:
            return Response(
                {'error': 'Reservation cannot be cancelled in current status'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if cancellation is allowed (e.g., not too close to reservation time)
        now = timezone.now()
        time_until_reservation = reservation.reservation_time - now
        
        if time_until_reservation < timedelta(hours=2):
            return Response(
                {'error': 'Reservations cannot be cancelled less than 2 hours before the scheduled time'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        reservation.status = 'cancelled'
        reservation.save()
        
        serializer = self.get_serializer(reservation)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def modify(self, request, pk=None):
        """Modify a reservation (change time, party size, etc.)."""
        reservation = self.get_object()
        
        if reservation.status not in ['confirmed']:
            return Response(
                {'error': 'Only confirmed reservations can be modified'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Use the create serializer for validation
        serializer = ReservationCreateSerializer(
            reservation, 
            data=request.data, 
            partial=True,
            context={'request': request}
        )
        
        if serializer.is_valid():
            serializer.save()
            # Return full reservation data
            full_serializer = ReservationSerializer(reservation, context={'request': request})
            return Response(full_serializer.data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """Get upcoming reservations for the user."""
        now = timezone.now()
        upcoming_reservations = self.request.user.core_reservations.filter(
            reservation_time__gte=now,
            status__in=['confirmed', 'seated']
        ).select_related(
            'service_type', 'table'
        ).order_by('-reservation_time')[:5]
        
        serializer = ReservationListSerializer(
            upcoming_reservations, 
            many=True, 
            context={'request': request}
        )
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def history(self, request):
        """Get reservation history for the user."""
        now = timezone.now()
        past_reservations = self.request.user.core_reservations.filter(
            Q(reservation_time__lt=now) | Q(status__in=['cancelled', 'completed', 'no_show'])
        ).select_related(
            'service_type', 'table'
        ).order_by('-reservation_time')[:20]
        
        serializer = ReservationListSerializer(
            past_reservations, 
            many=True, 
            context={'request': request}
        )
        return Response(serializer.data)


# Admin ViewSets for management
class AdminTableViewSet(viewsets.ModelViewSet):
    """Admin ViewSet for Table management."""
    serializer_class = TableSerializer
    permission_classes = [permissions.IsAdminUser]
    queryset = Table.objects.all().select_related('location').order_by('table_number')
    
    @action(detail=True, methods=['post'])
    def toggle_active(self, request, pk=None):
        """Toggle table active status."""
        table = self.get_object()
        table.is_active = not table.is_active
        table.save()
        
        serializer = self.get_serializer(table)
        return Response(serializer.data)


class AdminReservationViewSet(viewsets.ModelViewSet):
    """Admin ViewSet for Reservation management."""
    serializer_class = ReservationSerializer
    permission_classes = [permissions.IsAdminUser]
    
    def get_queryset(self):
        """Return all reservations for admin."""
        return Reservation.objects.all().select_related(
            'user', 'service_type', 'table'
        ).order_by('-reservation_time')
    
    @action(detail=True, methods=['post'])
    def mark_seated(self, request, pk=None):
        """Mark reservation as seated."""
        reservation = self.get_object()
        reservation.status = 'seated'
        reservation.save()
        
        serializer = self.get_serializer(reservation)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def mark_completed(self, request, pk=None):
        """Mark reservation as completed."""
        reservation = self.get_object()
        reservation.status = 'completed'
        reservation.save()
        
        serializer = self.get_serializer(reservation)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def mark_no_show(self, request, pk=None):
        """Mark reservation as no show."""
        reservation = self.get_object()
        reservation.status = 'no_show'
        reservation.save()
        
        serializer = self.get_serializer(reservation)
        return Response(serializer.data)