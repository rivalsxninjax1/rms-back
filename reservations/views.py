from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List, Optional

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticatedOrReadOnly, IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response

from .models import Table, Reservation
from .serializers import TableSerializer, ReservationSerializer


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    """
    Accepts:
      - "YYYY-MM-DDTHH:MM[:SS]"
      - "YYYY-MM-DD"
    Returns timezone-aware datetime in the current timezone.
    """
    if not value:
        return None
    try:
        # Accept "YYYY-MM-DDTHH:MM[:SS]"
        fmt = "%Y-%m-%dT%H:%M:%S" if len(value) >= 19 else "%Y-%m-%dT%H:%M"
        dt = datetime.strptime(value, fmt)
    except Exception:
        try:
            dt = datetime.strptime(value, "%Y-%m-%d")
            dt = dt.replace(hour=0, minute=0, second=0)
        except Exception:
            return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def _active_reservation_statuses() -> List[str]:
    """
    Normalize active statuses for overlap queries. If your model defines
    constants like STATUS_PENDING/STATUS_CONFIRMED or ACTIVE_STATUSES,
    we consume them; otherwise we default to ['pending', 'confirmed'].
    """
    # Preferred: explicit list on the model
    if hasattr(Reservation, "ACTIVE_STATUSES"):
        try:
            vals = list(getattr(Reservation, "ACTIVE_STATUSES"))
            return [str(v).lower() for v in vals]
        except Exception:
            pass

    # Fall back to common constant names
    pending = getattr(Reservation, "STATUS_PENDING", "pending")
    confirmed = getattr(Reservation, "STATUS_CONFIRMED", "confirmed")
    return [str(pending).lower(), str(confirmed).lower()]


class TableViewSet(viewsets.ModelViewSet):
    """
    Matches the original ZIP:
      - ModelViewSet
      - filterset on ['location', 'is_active', 'capacity']
    Extended to provide 'availability' for a time window via a custom action.
    """
    queryset = Table.objects.select_related("location").all()
    serializer_class = TableSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["location", "is_active", "capacity"]
    permission_classes = [IsAuthenticatedOrReadOnly]

    @action(detail=False, methods=["get"], url_path="availability")
    def availability(self, request: Request) -> Response:
        """
        GET /api/reservations/tables/availability/?location=<id>&start=...&end=...
        Returns [{id, table_number, capacity, is_free}, ...] for active tables.
        If end missing, default slot is 90 minutes.
        """
        try:
            location_id = int(request.query_params.get("location") or request.query_params.get("location_id") or 1)
        except Exception:
            return Response({"detail": "Invalid location id."}, status=status.HTTP_400_BAD_REQUEST)

        start = _parse_dt(request.query_params.get("start"))
        end = _parse_dt(request.query_params.get("end"))
        if not start:
            now = timezone.now()
            start = now + timedelta(minutes=15)
            # round to 15m
            minute = (start.minute // 15) * 15
            start = start.replace(minute=minute, second=0, microsecond=0)
        if not end:
            end = start + timedelta(minutes=90)

        active_statuses = _active_reservation_statuses()
        overlapping = set(
            Reservation.objects.filter(
                location_id=location_id,
                status__in=active_statuses,
                start_time__lt=end,
                end_time__gt=start,
            ).values_list("table_id", flat=True)
        )

        rows: List[Dict] = []
        for t in Table.objects.filter(location_id=location_id, is_active=True).order_by("table_number"):
            rows.append(
                {
                    "id": t.id,
                    "table_number": t.table_number,
                    "capacity": t.capacity,
                    "is_free": t.id not in overlapping,
                }
            )
        return Response({"tables": rows, "start": start.isoformat(), "end": end.isoformat()})


class ReservationViewSet(viewsets.ModelViewSet):
    """
    Matches the original ZIP:
      - ModelViewSet
      - filterset on ['location', 'status', 'reservation_date', 'table']
    Create is guarded by atomic overlap checks (transaction-safe).
    """
    queryset = Reservation.objects.select_related("location", "table", "created_by").all()
    serializer_class = ReservationSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["location", "status", "reservation_date", "table"]
    permission_classes = [IsAuthenticatedOrReadOnly]

    @transaction.atomic
    def create(self, request: Request, *args, **kwargs) -> Response:
        """
        Accepts either:
          - explicit start_time & end_time, or
          - start_time only (end_time defaults to +90 minutes)
        Also sets created_by = request.user if authenticated.
        Prevents double-booking with SELECT ... FOR UPDATE on conflicting rows.
        """
        data = dict(request.data)
        # Normalize incoming strings
        start_raw = data.get("start_time") or data.get("start") or ""
        end_raw = data.get("end_time") or data.get("end") or ""

        start = _parse_dt(str(start_raw))
        end = _parse_dt(str(end_raw)) if end_raw else None
        if not start:
            return Response({"detail": "start_time is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not end:
            end = start + timedelta(minutes=90)

        # Ensure serializer gets ISO strings for datetimes
        payload = {
            **data,
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
        }
        if request.user and request.user.is_authenticated:
            payload["created_by"] = request.user.id

        serializer = self.get_serializer(data=payload)
        serializer.is_valid(raise_exception=True)

        # Double-booking protection in DB transaction:
        table = serializer.validated_data["table"]
        location = serializer.validated_data["location"]
        s = serializer.validated_data["start_time"]
        e = serializer.validated_data["end_time"]

        # Sanity checks
        if table.location_id != location.id:
            return Response({"detail": "Table does not belong to selected location."}, status=status.HTTP_400_BAD_REQUEST)
        if e <= s:
            return Response({"detail": "end_time must be after start_time."}, status=status.HTTP_400_BAD_REQUEST)
        party_size = serializer.validated_data.get("party_size") or 1
        if party_size > getattr(table, "capacity", party_size):
            return Response({"detail": "Party size exceeds table capacity."}, status=status.HTTP_400_BAD_REQUEST)

        active_statuses = _active_reservation_statuses()
        conflicts = (
            Reservation.objects.select_for_update()
            .filter(location=location, table=table, status__in=active_statuses)
            .filter(Q(start_time__lt=e) & Q(end_time__gt=s))
        )
        if conflicts.exists():
            return Response({"detail": "Selected table is already booked in this time range."}, status=status.HTTP_409_CONFLICT)

        instance = serializer.save()
        headers = self.get_success_headers(serializer.data)
        return Response(ReservationSerializer(instance).data, status=status.HTTP_201_CREATED, headers=headers)

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    def confirm(self, request: Request, pk: str | None = None) -> Response:
        """
        Admin action: set status=confirmed
        """
        res = self.get_object()
        res.status = getattr(Reservation, "STATUS_CONFIRMED", "confirmed")
        res.save(update_fields=["status"])
        return Response({"ok": True, "status": res.status})

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    def cancel(self, request: Request, pk: str | None = None) -> Response:
        """
        Admin action: set status=cancelled
        """
        res = self.get_object()
        res.status = getattr(Reservation, "STATUS_CANCELLED", "cancelled")
        res.save(update_fields=["status"])
        return Response({"ok": True, "status": res.status})
