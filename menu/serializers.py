# menu/serializers.py
from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from rest_framework import serializers


def _abs_url(request, url: Optional[str]) -> Optional[str]:
    """Return an absolute URL if a request is available; otherwise the raw URL."""
    if not url:
        return None
    if request is None:
        return url
    try:
        return request.build_absolute_uri(url)
    except Exception:
        return url


class MenuItemSerializer(serializers.Serializer):
    """
    Minimal, stable shape used by storefront JS:

      {
        "id": 1,
        "name": "Veg Momo",
        "description": "Delicious…",
        "price": "199.00",        # numeric-friendly string
        "image": "https://…/media/menu_items/veg.jpg",
        "category": {"id": 2, "name": "Momos"},
        "is_vegetarian": true,
        "is_available": true,
        "preparation_time": 15
      }
    """
    id = serializers.IntegerField()
    name = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    category = serializers.SerializerMethodField()
    is_vegetarian = serializers.SerializerMethodField()
    is_available = serializers.SerializerMethodField()
    preparation_time = serializers.SerializerMethodField()

    # ---------------- name / description / price ----------------

    def get_name(self, obj: Any) -> str:
        for f in ("name", "title"):
            if hasattr(obj, f) and getattr(obj, f):
                return str(getattr(obj, f))
        return "Item"

    def get_description(self, obj: Any) -> str:
        for f in ("description", "details", "summary"):
            if hasattr(obj, f) and getattr(obj, f):
                return str(getattr(obj, f))
        return ""

    def get_price(self, obj: Any) -> str:
        """
        Return a Decimal-like value rendered as a numeric-friendly string.
        The storefront uses Number(item.price) so strings like "12.00" are fine.
        """
        for f in ("price", "unit_price", "amount"):
            if hasattr(obj, f):
                val = getattr(obj, f)
                # Normalize to Decimal, then to 2dp string
                try:
                    dec = Decimal(str(val))
                    return f"{dec:.2f}"
                except Exception:
                    pass
        return "0.00"

    # ---------------- image (absolute URL) ----------------

    def get_image(self, obj: Any) -> Optional[str]:
        request = self.context.get("request") if isinstance(self.context, dict) else None
        # Try common image-like fields
        for f in ("image", "photo", "picture", "thumbnail"):
            if hasattr(obj, f):
                val = getattr(obj, f)
                # File/ImageField or plain string path
                path = None
                try:
                    if val:
                        if hasattr(val, "url"):
                            path = val.url
                        else:
                            path = str(val)
                except Exception:
                    path = None
                if path:
                    return _abs_url(request, path)
        return None

    # ---------------- category ----------------

    def get_category(self, obj: Any) -> Optional[dict]:
        """
        Return minimal category info without assuming exact field names.
        """
        for f in ("category", "menu_category", "group"):
            if hasattr(obj, f) and getattr(obj, f):
                c = getattr(obj, f)
                name = getattr(c, "name", None) or getattr(c, "title", None)
                return {"id": getattr(c, "id", None), "name": name}
        return None

    # ---------------- flags / prep time ----------------

    def get_is_vegetarian(self, obj: Any) -> bool:
        return bool(getattr(obj, "is_vegetarian", False))

    def get_is_available(self, obj: Any) -> bool:
        return bool(getattr(obj, "is_available", True))

    def get_preparation_time(self, obj: Any) -> int:
        try:
            return int(getattr(obj, "preparation_time", 15) or 15)
        except Exception:
            return 15
