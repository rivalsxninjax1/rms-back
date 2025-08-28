from __future__ import annotations

from django.conf import settings
from django.db import models
from django.contrib.auth.models import AbstractUser, Group, Permission


class User(AbstractUser):
    """
    Custom user model. We keep it minimal to avoid breaking existing code.

    We explicitly redeclare 'groups' and 'user_permissions' with explicit 'through='
    models (User_groups, User_user_permissions) so Django knows the FK targets and
    avoids the admin/system-check errors you were seeing.
    """

    # Re-declare M2M to use explicit through models that we define below.
    groups = models.ManyToManyField(
        Group,
        verbose_name="groups",
        blank=True,
        help_text="The groups this user belongs to.",
        related_name="user_set",
        related_query_name="user",
        through="accounts.User_groups",
    )

    user_permissions = models.ManyToManyField(
        Permission,
        verbose_name="user permissions",
        blank=True,
        help_text="Specific permissions for this user.",
        related_name="user_set",
        related_query_name="user",
        through="accounts.User_user_permissions",
    )

    class Meta:
        swappable = "AUTH_USER_MODEL"

    def __str__(self) -> str:
        return self.get_username() or f"User#{self.pk}"


class User_groups(models.Model):
    """
    Explicit 'through' table linking accounts.User <-> auth.Group.
    Fixes: accounts.User_groups.user: (fields.E301) when using a swapped user model
    """
    # ---- MINIMAL FIX: point FK to the swapped user model ----
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    group = models.ForeignKey(Group, on_delete=models.CASCADE)

    class Meta:
        db_table = "accounts_user_groups"
        unique_together = (("user", "group"),)

    def __str__(self) -> str:
        return f"{self.user_id} ↔ {self.group_id}"


class User_user_permissions(models.Model):
    """
    Explicit 'through' table linking accounts.User <-> auth.Permission.
    Fixes: accounts.User_user_permissions.user: (fields.E301) when using a swapped user model
    """
    # ---- MINIMAL FIX: point FK to the swapped user model ----
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE)

    class Meta:
        db_table = "accounts_user_user_permissions"
        unique_together = (("user", "permission"),)

    def __str__(self) -> str:
        return f"{self.user_id} ↔ {self.permission_id}"
