from __future__ import annotations

from typing import Iterable

from django.contrib.auth.models import Group
from rest_framework.permissions import BasePermission, SAFE_METHODS


ROLE_MANAGER = "Manager"
ROLE_CASHIER = "Cashier"
ROLE_KITCHEN = "Kitchen"
ROLE_HOST = "Host"

ALL_ROLES = (ROLE_MANAGER, ROLE_CASHIER, ROLE_KITCHEN, ROLE_HOST)


def user_in_group(user, group_name: str) -> bool:
    try:
        if not user or not getattr(user, "is_authenticated", False):
            return False
        return user.groups.filter(name=group_name).exists()
    except Exception:
        return False


def user_roles(user) -> list[str]:
    if not user or not getattr(user, "is_authenticated", False):
        return []
    try:
        return list(user.groups.values_list("name", flat=True))
    except Exception:
        return []


class IsManagerOrReadOnly(BasePermission):
    """Write access only for Managers; read allowed to everyone."""

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return user_in_group(request.user, ROLE_MANAGER)

