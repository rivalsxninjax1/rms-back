from __future__ import annotations

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import User, User_groups, User_user_permissions


class UserGroupsInline(admin.TabularInline):
    """
    Manage the explicit through table between accounts.User and auth.Group.
    Using raw_id_fields to avoid needing a custom Group admin.
    """
    model = User_groups
    extra = 0
    raw_id_fields = ("group",)
    verbose_name = "Group membership"
    verbose_name_plural = "Group memberships"


class UserUserPermissionsInline(admin.TabularInline):
    """
    Manage the explicit through table between accounts.User and auth.Permission.
    Using raw_id_fields to avoid needing a custom Permission admin.
    """
    model = User_user_permissions
    extra = 0
    raw_id_fields = ("permission",)
    verbose_name = "User permission"
    verbose_name_plural = "User permissions"


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """
    Custom User admin that avoids admin.E013 by NOT placing the ManyToMany
    fields (groups, user_permissions) directly in fieldsets or filter_horizontal
    when those M2Ms use an explicit `through=` model.

    Instead, we expose two inlines:
      - UserGroupsInline for memberships
      - UserUserPermissionsInline for direct user permissions
    """

    # Keep the common list configuration
    list_display = ("username", "email", "first_name", "last_name", "is_staff", "is_active")
    list_filter = ("is_staff", "is_superuser", "is_active")

    # IMPORTANT: Remove groups/user_permissions from fieldsets entirely.
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        (_("Personal info"), {"fields": ("first_name", "last_name", "email")}),
        (_("Permissions"), {"fields": ("is_active", "is_staff", "is_superuser")}),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("username", "password1", "password2", "email", "first_name", "last_name"),
            },
        ),
    )

    search_fields = ("username", "first_name", "last_name", "email")
    ordering = ("username",)

    # CRITICAL: must not reference M2Ms with through=
    filter_horizontal: tuple = ()

    # Use inlines to manage the explicit through relationships
    inlines = [UserGroupsInline, UserUserPermissionsInline]
