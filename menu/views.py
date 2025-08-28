from __future__ import annotations

import json
from typing import Any, Dict, List

from django.db.models import Prefetch, Q
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST
from django.utils.decorators import method_decorator

from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import MenuCategory, MenuItem
from .serializers import MenuItemSerializer

# -----------------------------------------------------------------------------
# Serializers (lightweight for categories)
# -----------------------------------------------------------------------------

from rest_framework import serializers


class MenuCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = MenuCategory
        fields = ["id", "organization", "name", "description", "image", "sort_order", "is_active", "created_at"]


# -----------------------------------------------------------------------------
# ViewSets
# -----------------------------------------------------------------------------

class MenuItemViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only items list/detail for storefront.
    Supports filters:
      - organization, category, is_available, is_vegetarian
    """
    permission_classes = [AllowAny]
    serializer_class = MenuItemSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["organization", "category", "is_available", "is_vegetarian"]
    search_fields = ["name", "description"]
    ordering_fields = ["sort_order", "name", "price", "created_at"]
    ordering = ["sort_order", "name"]

    def get_queryset(self):
        qs = (
            MenuItem.objects
            .select_related("category", "organization")
            .filter(is_available=True)
            .order_by("sort_order", "name")
        )
        return qs

    def list(self, request: Request, *args, **kwargs) -> Response:
        qs = self.filter_queryset(self.get_queryset())
        ser = self.get_serializer(qs, many=True, context={"request": request})
        return Response(ser.data)

    def retrieve(self, request: Request, *args, **kwargs) -> Response:
        obj = self.get_queryset().get(pk=kwargs.get("pk"))
        ser = self.get_serializer(obj, context={"request": request})
        return Response(ser.data)


class MenuCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [AllowAny]
    serializer_class = MenuCategorySerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_fields = ["organization", "is_active"]
    search_fields = ["name", "description"]
    ordering_fields = ["sort_order", "name", "created_at"]
    ordering = ["sort_order", "name"]

    def get_queryset(self):
        return MenuCategory.objects.filter(is_active=True).order_by("sort_order", "name")


# -----------------------------------------------------------------------------
# Minimal server-side cart endpoints (optional; session-backed)
# -----------------------------------------------------------------------------

SESSION_CART_KEY = "server_cart_v1"


def _session_cart_get(request: HttpRequest) -> Dict[str, Any]:
    try:
        data = request.session.get(SESSION_CART_KEY) or {}
        items = data.get("items") or {}
        tip = int(data.get("tip_cents") or 0)
        discount = int(data.get("discount_cents") or 0)
        delivery = (data.get("delivery") or "DINE_IN").upper()
        return {"items": items, "tip_cents": tip, "discount_cents": discount, "delivery": delivery}
    except Exception:
        return {"items": {}, "tip_cents": 0, "discount_cents": 0, "delivery": "DINE_IN"}


def _session_cart_set(request: HttpRequest, payload: Dict[str, Any]) -> None:
    request.session[SESSION_CART_KEY] = payload
    request.session.modified = True


class CartView(APIView):
    """
    GET returns the current server-side cart snapshot (if you decide to use it).
    Structure:
      {
        items: [{id, qty, name, price, image}],
        tip: <float>, discount: <float>, delivery: "DINE_IN" | "UBER_EATS" | "DOORDASH"
      }
    Prices are looked up authoritatively from DB.
    """
    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
        state = _session_cart_get(request)
        items = []
        ids = [int(k) for k in (state["items"] or {}).keys() if str(k).isdigit()]
        db = {m.id: m for m in MenuItem.objects.filter(id__in=ids)}
        for sid, qty in (state["items"] or {}).items():
            try:
                iid = int(sid)
                q = int(qty or 0)
                if q <= 0 or iid not in db:
                    continue
                m = db[iid]
                items.append(
                    {
                        "id": m.id,
                        "qty": q,
                        "name": m.name,
                        "price": float(m.price),
                        "image": getattr(getattr(m, "image", None), "url", None),
                    }
                )
            except Exception:
                continue
        return Response(
            {
                "items": items,
                "tip": (state["tip_cents"] or 0) / 100.0,
                "discount": (state["discount_cents"] or 0) / 100.0,
                "delivery": state["delivery"],
            }
        )


class CartMergeView(APIView):
    """
    POST body: {
      items: [{id, qty, ...}],
      tip, discount, delivery
    }
    Merges guest cart into a session-backed server cart. This enables the
    "mergeIntoServerIfSupported" client helper to work without 404s.
    """
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        try:
            data = request.data
        except Exception:
            return Response({"detail": "Invalid JSON."}, status=400)

        state = _session_cart_get(request)
        merged: Dict[str, int] = dict(state["items"] or {})
        for it in data.get("items", []) or []:
            try:
                iid = int(it.get("id"))
                qty = int(it.get("qty") or 0)
                if qty <= 0:
                    continue
                merged[str(iid)] = int(merged.get(str(iid), 0)) + qty
            except Exception:
                continue

        tip_cents = int(round(float(data.get("tip") or data.get("tip_cents") or 0) * 100))
        discount_cents = int(round(float(data.get("discount") or data.get("discount_cents") or 0) * 100))
        delivery = (data.get("delivery") or state["delivery"] or "DINE_IN").upper()

        _session_cart_set(
            request,
            {"items": merged, "tip_cents": max(0, tip_cents), "discount_cents": max(0, discount_cents), "delivery": delivery},
        )
        return Response({"ok": True})
