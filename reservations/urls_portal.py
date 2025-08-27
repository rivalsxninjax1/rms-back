from django.urls import path
from .views_portal import reserve_page, AvailabilityView, CreateReservationView
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.utils import timezone
# Resolve models lazily from the app registry to avoid circular imports.
from django.apps import apps as _apps

Table = _apps.get_model("reservations", "Table")
ReservationHold = _apps.get_model("engagement", "ReservationHold")

app_name = "reservations_portal"

urlpatterns = [
    path("", reserve_page, name="page"),
    path("api/availability/", AvailabilityView.as_view(), name="availability"),
    path("api/reservations/", CreateReservationView.as_view(), name="create"),
]

# Simple hold API – quick function view here for minimal risk
@csrf_exempt
@login_required
def create_hold_view(request):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "POST required"}, status=405)
    try:
        body = json.loads(request.body.decode() or "{}")
    except Exception:
        body = {}
    table_id = body.get("table_id")
    try:
        table = Table.objects.get(pk=table_id, is_active=True)
    except Table.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Invalid table"}, status=400)
    hold = ReservationHold.create_or_refresh(table=table, user=request.user)
    return JsonResponse({"ok": True, "hold_id": hold.id, "expires_at": hold.expires_at.isoformat()})

urlpatterns += [
    path("api/holds/create/", create_hold_view, name="create_hold"),
]
