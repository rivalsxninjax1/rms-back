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
from .serializers import TableSerializer, ReservationSerializer, WalkInReservationSerializer


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
        GET /api/reservations/tables/availability/
          ?date=YYYY-MM-DD&from=HH:MM&to=HH:MM&location=<id>

        Also supports legacy params: start=<ISO>, end=<ISO>.

        Returns per-table blocks:
          {
            table_id, table_number, capacity, is_active,
            busy: [{start, end, reservation_id}],
            free: [{start, end}]  # derived within requested window
          }
        """
        # Location
        try:
            location_id = int(request.query_params.get("location") or request.query_params.get("location_id") or 1)
        except Exception:
            return Response({"detail": "Invalid location id."}, status=status.HTTP_400_BAD_REQUEST)

        # Time window: prefer (date, from, to); fallback to (start, end)
        date_str = request.query_params.get("date")
        from_str = request.query_params.get("from")
        to_str = request.query_params.get("to")

        def _combine(d: str, h: str) -> Optional[datetime]:
            try:
                dt = datetime.strptime(f"{d}T{h}", "%Y-%m-%dT%H:%M")
                if timezone.is_naive(dt):
                    dt = timezone.make_aware(dt, timezone.get_current_timezone())
                return dt
            except Exception:
                return None

        start = end = None
        if date_str and from_str and to_str:
            start = _combine(date_str, from_str)
            end = _combine(date_str, to_str)
        else:
            start = _parse_dt(request.query_params.get("start"))
            end = _parse_dt(request.query_params.get("end"))

        # Defaults
        if not start:
            # round upcoming quarter-hour
            now = timezone.now() + timedelta(minutes=15)
            minute = (now.minute // 15) * 15
            start = now.replace(minute=minute, second=0, microsecond=0)
        if not end:
            end = start + timedelta(minutes=90)

        # Gather active reservations overlapping window
        active_statuses = _active_reservation_statuses()
        res_qs = (
            Reservation.objects.select_related("table")
            .filter(
                location_id=location_id,
                status__in=active_statuses,
                start_time__lt=end,
                end_time__gt=start,
            )
            .only("id", "start_time", "end_time", "table_id")
        )

        busy_by_table: Dict[int, List[Dict]] = {}
        for r in res_qs:
            busy_by_table.setdefault(r.table_id, []).append({
                "start": timezone.localtime(r.start_time).isoformat(),
                "end": timezone.localtime(r.end_time).isoformat(),
                "reservation_id": r.id,
            })
        # Sort busy intervals per table by start
        for arr in busy_by_table.values():
            arr.sort(key=lambda x: x["start"])  # isoformat preserves order

        # Compose table blocks
        blocks: List[Dict] = []
        tables = Table.objects.select_related("location").filter(location_id=location_id).order_by("table_number")
        for t in tables:
            busy = busy_by_table.get(t.id, [])
            # derive free windows
            free: List[Dict] = []
            cur_start = start
            for b in busy:
                b_start = _parse_dt(b["start"]) or start
                if cur_start < b_start:
                    free.append({"start": cur_start.isoformat(), "end": b_start.isoformat()})
                b_end = _parse_dt(b["end"]) or end
                if b_end > cur_start:
                    cur_start = b_end
            if cur_start < end:
                free.append({"start": cur_start.isoformat(), "end": end.isoformat()})

            blocks.append({
                "table_id": t.id,
                "table_number": getattr(t, "table_number", ""),
                "capacity": getattr(t, "capacity", None),
                "is_active": getattr(t, "is_active", True),
                "busy": busy,
                "free": free,
            })

        return Response({
            "start": start.isoformat(),
            "end": end.isoformat(),
            "tables": blocks,
        })


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

    @action(detail=False, methods=["post"], url_path="walkin")
    @transaction.atomic
    def walkin(self, request: Request) -> Response:
        """
        Create a walk-in reservation starting in 5 minutes for a fixed duration (default 90m).
        Body: {table_id, minutes=90, guest_name?, party_size?, phone?}
        Sets status=confirmed and created_by=request.user (if authenticated).
        Returns 409 if the time window overlaps an active reservation.
        """
        ser = WalkInReservationSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        table = data["_table_obj"]
        location = data["_location_obj"]
        minutes = int(data.get("minutes") or 90)
        guest_name = data.get("guest_name") or ""
        guest_phone = data.get("phone") or ""
        party_size = int(data.get("party_size") or 2)

        # Compute window
        start = timezone.now() + timedelta(minutes=5)
        end = start + timedelta(minutes=minutes)

        # Conflict check (atomic)
        active_statuses = _active_reservation_statuses()
        conflicts = (
            Reservation.objects.select_for_update()
            .filter(location=location, table=table, status__in=active_statuses)
            .filter(Q(start_time__lt=end) & Q(end_time__gt=start))
        )
        if conflicts.exists():
            return Response({"detail": "Selected table is already booked in this time range."}, status=status.HTTP_409_CONFLICT)

        # Create reservation
        res = Reservation(
            location=location,
            table=table,
            created_by=request.user if request.user and request.user.is_authenticated else None,
            guest_name=guest_name,
            guest_phone=guest_phone,
            party_size=party_size,
            start_time=start,
            end_time=end,
            status=getattr(Reservation, "STATUS_CONFIRMED", "confirmed"),
        )
        # Model.save() will validate reservation_date & overlap again
        res.save()
        return Response(ReservationSerializer(res).data, status=status.HTTP_201_CREATED)

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

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    def check_in(self, request: Request, pk: str | None = None) -> Response:
        """Admin: mark reservation as seated/confirmed."""
        res = self.get_object()
        now = timezone.now()
        res.status = getattr(Reservation, "STATUS_CONFIRMED", "confirmed")
        update_fields = ["status"]
        if hasattr(res, "seated_at"):
            if not getattr(res, "seated_at"):
                res.seated_at = now  # type: ignore[attr-defined]
            update_fields.append("seated_at")
        if hasattr(res, "confirmed_at"):
            if not getattr(res, "confirmed_at"):
                res.confirmed_at = now  # type: ignore[attr-defined]
            update_fields.append("confirmed_at")
        res.save(update_fields=update_fields)  # type: ignore[arg-type]
        return Response({"ok": True, "status": res.status, "seated_at": getattr(res, "seated_at", None)})

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    def check_out(self, request: Request, pk: str | None = None) -> Response:
        """Admin: mark reservation as completed/checked-out."""
        res = self.get_object()
        now = timezone.now()
        res.status = getattr(Reservation, "STATUS_COMPLETED", "completed")
        if hasattr(res, "completed_at"):
            res.completed_at = now
            res.save(update_fields=["status", "completed_at"])  # type: ignore
        else:
            res.save(update_fields=["status"])  # type: ignore
        return Response({"ok": True, "status": res.status})

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    def no_show(self, request: Request, pk: str | None = None) -> Response:
        """Admin: mark reservation as no-show."""
        res = self.get_object()
        res.status = getattr(Reservation, "STATUS_NO_SHOW", "no_show")
        res.save(update_fields=["status"])  # type: ignore
        return Response({"ok": True, "status": res.status})

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    def mark_deposit_paid(self, request: Request, pk: str | None = None) -> Response:
        res = self.get_object()
        if getattr(res, "deposit_amount", 0) and hasattr(res, "deposit_paid"):
            res.deposit_paid = True
            res.save(update_fields=["deposit_paid"])  # type: ignore
        return Response({"ok": True, "deposit_paid": getattr(res, "deposit_paid", False)})

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    def mark_deposit_unpaid(self, request: Request, pk: str | None = None) -> Response:
        res = self.get_object()
        if getattr(res, "deposit_amount", 0) and hasattr(res, "deposit_paid"):
            res.deposit_paid = False
            res.save(update_fields=["deposit_paid"])  # type: ignore
        return Response({"ok": True, "deposit_paid": getattr(res, "deposit_paid", False)})

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    def create_hold(self, request: Request, pk: str | None = None) -> Response:
        """Admin: create/extend a 20-minute hold for the reservation's table."""
        try:
            from engagement.models import ReservationHold
        except Exception:
            return Response({"detail": "ReservationHold model not available"}, status=400)
        res = self.get_object()
        if not res.table_id:
            return Response({"detail": "Reservation has no table"}, status=400)
        expires = timezone.now() + timedelta(minutes=20)
        hold, _ = ReservationHold.objects.get_or_create(
            table_id=res.table_id,
            status=ReservationHold.STATUS_PENDING,
            defaults={"expires_at": expires}
        )
        if hold.expires_at < expires:
            hold.expires_at = expires
            hold.save(update_fields=["expires_at"])  # type: ignore
        return Response({"ok": True, "hold_id": hold.id, "expires_at": hold.expires_at})
