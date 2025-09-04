from __future__ import annotations

from typing import Dict, Iterable, List, Tuple

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

from core.permissions import ALL_ROLES, ROLE_MANAGER, ROLE_CASHIER, ROLE_KITCHEN, ROLE_HOST


def ensure_group(name: str) -> Group:
    g, _ = Group.objects.get_or_create(name=name)
    return g


def add_perms(group: Group, perms: Iterable[Permission]) -> None:
    for p in perms:
        group.permissions.add(p)


def model_perms(app_label: str, model: str, actions: Iterable[str]) -> List[Permission]:
    ct = ContentType.objects.get(app_label=app_label, model=model)
    out: List[Permission] = []
    for action in actions:
        codename = f"{action}_{model}"
        try:
            p = Permission.objects.get(content_type=ct, codename=codename)
            out.append(p)
        except Permission.DoesNotExist:
            continue
    return out


def seed_permissions() -> Dict[str, Group]:
    # Create groups
    groups = {name: ensure_group(name) for name in ALL_ROLES}

    # Menu app permissions
    menu_models = ("menuitem", "menucategory")
    manager_menu_perms = []
    for m in menu_models:
        manager_menu_perms += model_perms("menu", m, ("view", "add", "change", "delete"))
    add_perms(groups[ROLE_MANAGER], manager_menu_perms)

    cashier_menu_perms = []
    for m in menu_models:
        cashier_menu_perms += model_perms("menu", m, ("view",))
    add_perms(groups[ROLE_CASHIER], cashier_menu_perms)

    host_menu_perms = []
    for m in menu_models:
        host_menu_perms += model_perms("menu", m, ("view",))
    add_perms(groups[ROLE_HOST], host_menu_perms)

    kitchen_menu_perms = []
    for m in menu_models:
        kitchen_menu_perms += model_perms("menu", m, ("view",))
    add_perms(groups[ROLE_KITCHEN], kitchen_menu_perms)

    # Orders app
    orders_models = ("order", "orderitem")
    manager_orders = []
    cashier_orders = []
    kitchen_orders = []
    for m in orders_models:
        manager_orders += model_perms("orders", m, ("view", "add", "change", "delete"))
        cashier_orders += model_perms("orders", m, ("view", "add", "change"))
    # Kitchen can view and change OrderItem (status updates), and view Orders
    kitchen_orders += model_perms("orders", "orderitem", ("view", "change"))
    kitchen_orders += model_perms("orders", "order", ("view",))

    add_perms(groups[ROLE_MANAGER], manager_orders)
    add_perms(groups[ROLE_CASHIER], cashier_orders)
    add_perms(groups[ROLE_KITCHEN], kitchen_orders)

    # Reservations app (Host focus)
    res_models = ("reservation",)
    host_res = []
    for m in res_models:
        host_res += model_perms("reservations", m, ("view", "add", "change"))
    add_perms(groups[ROLE_HOST], host_res)
    # Manager oversight
    manager_res = []
    for m in res_models:
        manager_res += model_perms("reservations", m, ("view", "add", "change", "delete"))
    add_perms(groups[ROLE_MANAGER], manager_res)

    return groups


class Command(BaseCommand):
    help = "Seed RBAC roles (Groups) and demo users: Manager, Cashier, Kitchen, Host."

    def add_arguments(self, parser):
        parser.add_argument("--create-users", action="store_true", help="Also create demo users and assign roles")
        parser.add_argument("--password", type=str, default="ChangeMe123!", help="Password to set for all demo users")

    def handle(self, *args, **options):
        groups = seed_permissions()
        self.stdout.write(self.style.SUCCESS("Groups and permissions seeded."))

        if options["create_users"]:
            User = get_user_model()
            password = options["password"]
            demos = [
                ("manager", "manager@example.com", ROLE_MANAGER),
                ("cashier", "cashier@example.com", ROLE_CASHIER),
                ("kitchen", "kitchen@example.com", ROLE_KITCHEN),
                ("host", "host@example.com", ROLE_HOST),
            ]
            for username, email, role in demos:
                user, created = User.objects.get_or_create(
                    username=username,
                    defaults={"email": email}
                )
                if created:
                    user.set_password(password)
                    user.save()
                g = groups[role]
                user.groups.add(g)
                self.stdout.write(self.style.SUCCESS(f"User '{username}' in group '{role}'"))
            self.stdout.write(self.style.WARNING(f"Demo users created with password: {password}"))

