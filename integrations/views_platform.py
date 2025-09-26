from __future__ import annotations

import json
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from .providers.ubereats import UberEatsClient
from .providers.doordash import DoorDashClient
from .providers.grubhub import GrubhubClient
from .services import handle_webhook, push_menu, update_item_availability


@csrf_exempt
@require_POST
def ubereats_webhook(request):
    raw = request.body or b""
    sig = request.META.get("HTTP_X_UBER_SIGNATURE", "") or request.META.get("HTTP_X_SIGNATURE", "")
    if not UberEatsClient.verify_webhook(sig, raw):
        return HttpResponse("Invalid signature", status=400)
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception:
        return HttpResponse("Invalid JSON", status=400)
    event = data.get("event") or data.get("type") or ""
    result = handle_webhook("UBEREATS", event, data)
    return JsonResponse(result)


@csrf_exempt
@require_POST
def doordash_webhook(request):
    raw = request.body or b""
    sig = request.META.get("HTTP_X_DD_SIGNATURE", "") or request.META.get("HTTP_X_SIGNATURE", "")
    if not DoorDashClient.verify_webhook(sig, raw):
        return HttpResponse("Invalid signature", status=400)
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception:
        return HttpResponse("Invalid JSON", status=400)
    event = data.get("event") or data.get("type") or ""
    result = handle_webhook("DOORDASH", event, data)
    return JsonResponse(result)


@csrf_exempt
@require_POST
def grubhub_webhook(request):
    raw = request.body or b""
    sig = request.META.get("HTTP_X_GH_SIGNATURE", "") or request.META.get("HTTP_X_SIGNATURE", "")
    if not GrubhubClient.verify_webhook(sig, raw):
        return HttpResponse("Invalid signature", status=400)
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception:
        return HttpResponse("Invalid JSON", status=400)
    event = data.get("event") or data.get("type") or ""
    result = handle_webhook("GRUBHUB", event, data)
    return JsonResponse(result)
