from __future__ import annotations
from datetime import datetime, timedelta
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import render
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.conf import settings
import stripe
stripe.api_key = getattr(settings, "STRIPE_SECRET_KEY", "")
from django.http import JsonResponse

from .models import Table, Reservation
from .serializers_portal import (
    TableStatusSerializer,
    CreateReservationSerializer,
    ReservationSerializer,
)

# derive “20-minute hold after checkout” from existing Orders/Payments
def _current_dinein_busy_map(slot_start=None, slot_end=None, now=None):
    """
    Treat active holds as temporary busy states, but only when the requested
    time window overlaps the hold window. This ensures holds only affect
    "this day / this time" and do not block other days/times.
    """
    from engagement.models import ReservationHold
    now = now or timezone.now()
    # Normalize inputs to timezone-aware datetimes to avoid naive/aware comparisons
    if slot_start is not None and timezone.is_naive(slot_start):
        slot_start = timezone.make_aware(slot_start, timezone.get_current_timezone())
    if slot_end is not None and timezone.is_naive(slot_end):
        slot_end = timezone.make_aware(slot_end, timezone.get_current_timezone())
    qs = ReservationHold.objects.filter(status="PENDING")
    if slot_start is not None and slot_end is not None:
        qs = qs.filter(created_at__lt=slot_end, expires_at__gt=slot_start)
    else:
        qs = qs.filter(expires_at__gt=now)
    qs = qs.select_related("table")

    busy = {}
    for h in qs:
        tnum = str(getattr(h.table, "table_number", ""))
        # Compute overlap seconds between [created_at, expires_at] and [slot_start, slot_end] or [now, expires_at]
        s0 = h.created_at
        e0 = h.expires_at
        if timezone.is_naive(s0):
            s0 = timezone.make_aware(s0, timezone.get_current_timezone())
        if timezone.is_naive(e0):
            e0 = timezone.make_aware(e0, timezone.get_current_timezone())
        s1 = slot_start or now
        e1 = slot_end or e0
        try:
            overlap = max(0, int((min(e0, e1) - max(s0, s1)).total_seconds()))
        except Exception:
            overlap = 0
        if tnum and overlap > 0:
            busy[tnum] = max(busy.get(tnum, 0), overlap)
    return busy

def _parse_dt(date_str: str, time_str: str) -> datetime:
    # Build timezone-aware datetime to match DB datetimes
    dt = datetime.fromisoformat(f"{date_str}T{time_str}")
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt

def _active_reservations(slot_dt: datetime, end_dt: datetime | None = None):
    """
    If end_dt provided, return reservations overlapping [slot_dt, end_dt].
    Otherwise, return reservations within ±90 minutes of slot_dt.
    Excludes terminal states.
    """
    if end_dt is not None and end_dt > slot_dt:
        start, end = slot_dt, end_dt
    else:
        margin = timedelta(minutes=90)
        start = slot_dt - margin
        end = slot_dt + margin
    return (
        Reservation.objects
        .filter(start_time__lt=end, end_time__gt=start)
        .exclude(status__in=["cancelled", "completed", "no_show"])
        .select_related("table")
    )

@login_required(login_url="/")
def reserve_page(request):
    return render(request, "reservations/reserve.html", {})

class AvailabilityView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        date = request.query_params.get("date")
        time = request.query_params.get("time")
        end_time = request.query_params.get("end")
        if not date or not time:
            return Response({"detail": "date and time are required"}, status=400)

        try:
            slot_dt = _parse_dt(date, time)
            end_dt = _parse_dt(date, end_time) if end_time else None
        except ValueError:
            return Response({"detail": "Invalid date/time format."}, status=400)
        # Robustness: if provided end is earlier than start (e.g., 05:00 vs 19:00),
        # treat it as next-day end instead of erroring.
        if end_dt is not None and end_dt <= slot_dt:
            end_dt = end_dt + timedelta(days=1)

        # Map: table_id -> Reservation overlapping requested window
        res_map = {r.table_id: r for r in _active_reservations(slot_dt, end_dt)}

        busy_map = _current_dinein_busy_map(slot_dt, end_dt)  # table_number -> seconds overlap

        payload = []
        for t in Table.objects.filter(is_active=True):
            status = "available"
            hold_seconds = None
            res_id = None
            res_status = ""

            # Busy due to 20m dine-in turnover
            if str(t.table_number) in busy_map and busy_map[str(t.table_number)] > 0:
                status = "busy"
                hold_seconds = busy_map[str(t.table_number)]

            # Reserved in the requested slot
            if t.id in res_map:
                status = "reserved"
                res_id = res_map[t.id].id
                res_status = res_map[t.id].status

            payload.append({
                "id": t.id,
                "table_number": t.table_number,
                "capacity": t.capacity,
                "status": status,
                "hold_seconds": hold_seconds,
                "reservation_id": res_id,
                "reservation_status": res_status,
            })

        return Response(TableStatusSerializer(payload, many=True).data, status=200)

class CreateReservationView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        ser = CreateReservationSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        table = Table.objects.select_for_update().get(pk=ser.validated_data["table_id"])
        start_dt = _parse_dt(
            ser.validated_data["date"].isoformat(),
            ser.validated_data["time"].isoformat(timespec="minutes"),
        )
        if ser.validated_data.get("end_time"):
            end_dt = _parse_dt(
                ser.validated_data["date"].isoformat(),
                ser.validated_data["end_time"].isoformat(timespec="minutes"),
            )
        else:
            end_dt = start_dt + timedelta(minutes=90)

        # deny if dine-in turnover busy
        busy_map = _current_dinein_busy_map(start_dt, end_dt)
        if str(table.table_number) in busy_map and busy_map[str(table.table_number)] > 0:
            return Response({"detail": "Table busy (turnover). Try later or another table."}, status=409)

        # deny if another reservation blocks the requested window
        if _active_reservations(start_dt, end_dt).filter(table=table).exists():
            return Response({"detail": "Table reserved at that time."}, status=409)

        # Enforce per-user simultaneous reservation cap
        user = request.user
        if user and user.is_authenticated:
            max_tables = int(getattr(settings, 'RESERVATION_MAX_TABLES', 1) or 1)
            if max_tables > 0:
                overlapping_count = Reservation.objects.filter(
                    created_by=user,
                    status__in=["pending", "confirmed"],
                    start_time__lt=end_dt,
                    end_time__gt=start_dt,
                ).select_for_update().count()
                if overlapping_count >= max_tables:
                    return Response({"detail": f"You already have {overlapping_count} active reservation(s) for that time window (limit {max_tables})."}, status=409)

        # Determine deposit requirement
        deposit_flat = float(getattr(settings, 'RESERVATION_DEPOSIT_FLAT_TOTAL', 0) or 0)
        deposit_per_seat = float(getattr(settings, 'RESERVATION_DEPOSIT_PER_SEAT', 0) or 0)
        # No-show policy enforcement
        action = str(getattr(settings, 'RESERVATION_NO_SHOW_ACTION', 'require_prepayment') or 'require_prepayment').lower()
        max_no_shows = int(getattr(settings, 'RESERVATION_MAX_NO_SHOWS', 3) or 3)
        enforce_prepay = False
        if user and user.is_authenticated and max_no_shows > 0:
            ns = Reservation.objects.filter(created_by=user, status='no_show').count()
            if ns >= max_no_shows:
                if action == 'block':
                    return Response({"detail": "Your account is blocked from new bookings due to repeated no-shows."}, status=403)
                elif action == 'require_prepayment':
                    enforce_prepay = True

        party_size = int(ser.validated_data["party_size"])
        total_deposit = 0.0
        # Flat total deposit takes precedence if configured (>0)
        if deposit_flat > 0:
            total_deposit = round(float(deposit_flat), 2)
        elif enforce_prepay or deposit_per_seat > 0:
            # Fall back to per-seat (or legacy flat $5/seat when enforced)
            per = deposit_per_seat if deposit_per_seat > 0 else 5.0
            total_deposit = round(per * max(1, party_size), 2)

        # Create reservation; attach deposit fields
        reservation = ser.save()
        if total_deposit > 0:
            reservation.deposit_amount = total_deposit
            reservation.deposit_paid = False
            reservation.deposit_applied = False
            reservation.save(update_fields=["deposit_amount", "deposit_paid", "deposit_applied"])

        # If a deposit is required and Stripe is configured, create a Checkout Session
        if total_deposit > 0 and getattr(settings, 'STRIPE_SECRET_KEY', ''):
            try:
                currency = getattr(settings, 'STRIPE_CURRENCY', 'usd').lower()
                # Build success/cancel using the current host to preserve session cookies
                base = request.build_absolute_uri("/").rstrip("/")
                # Include session id in redirect so we can verify and mark deposit_paid
                success_url = f"{base}/reserve/?deposit=success&session_id={{CHECKOUT_SESSION_ID}}"
                cancel_url = f"{base}/reserve/?deposit=cancel"
                session = stripe.checkout.Session.create(
                    mode="payment",
                    payment_method_types=["card"],
                    line_items=[{
                        "price_data": {
                            "currency": currency,
                            "product_data": {"name": f"Reservation deposit (x{party_size})"},
                            "unit_amount": int(round(total_deposit * 100)),
                        },
                        "quantity": 1,
                    }],
                    metadata={"reservation_id": str(reservation.id)},
                    success_url=success_url,
                    cancel_url=cancel_url,
                )
                data = ReservationSerializer(reservation).data
                data.update({
                    "deposit_required": True,
                    "deposit_amount": total_deposit,
                    "checkout_url": session.get("url"),
                })
                return Response(data, status=201)
            except Exception as e:
                data = ReservationSerializer(reservation).data
                data.update({
                    "deposit_required": True,
                    "deposit_amount": total_deposit,
                    "error": f"Stripe error: {e}",
                })
                return Response(data, status=201)

        # No deposit flow
        return Response(ReservationSerializer(reservation).data, status=201)


def deposit_success_view(request):
    """Simple endpoint to mark deposit as paid after Stripe redirects back.
    Verifies the Checkout Session by id (?session_id=cs_test_...).
    """
    session_id = request.GET.get("session_id")
    if not session_id or not getattr(settings, 'STRIPE_SECRET_KEY', ''):
        # Graceful fallback
        return JsonResponse({"ok": False, "detail": "Missing session_id or Stripe is not configured."}, status=400)
    try:
        sess = stripe.checkout.Session.retrieve(session_id)
        md = sess.get("metadata") or {}
        rid = md.get("reservation_id")
        if not rid:
            return JsonResponse({"ok": False, "detail": "Reservation id missing from session metadata."}, status=400)
        if sess.get("payment_status") not in ("paid", "complete") and sess.get("status") != "complete":
            return JsonResponse({"ok": False, "detail": "Payment not completed yet."}, status=400)
        try:
            r = Reservation.objects.get(pk=int(rid))
        except Reservation.DoesNotExist:
            return JsonResponse({"ok": False, "detail": "Reservation not found."}, status=404)
        if not r.deposit_paid:
            r.deposit_paid = True
            r.save(update_fields=["deposit_paid"])
        return JsonResponse({"ok": True, "reservation_id": r.id, "deposit_paid": True})
    except Exception as e:
        return JsonResponse({"ok": False, "detail": f"Stripe error: {e}"}, status=400)
