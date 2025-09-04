from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Dangerous: Delete all tables (and related reservations/holds), then seed fresh tables."

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=6, help="Number of tables to seed (default: 6)")
        parser.add_argument("--yes", action="store_true", help="Confirm destructive operation")

    def handle(self, *args, **opts):
        count = int(opts["count"])
        if not opts["yes"]:
            self.stdout.write(self.style.WARNING("This will DELETE all reservations, holds, and tables."))
            self.stdout.write(self.style.WARNING("Re-run with --yes to proceed."))
            return

        from core.models import Table
        from reservations.models import Reservation
        from engagement.models import ReservationHold
        from orders.models import Cart, Order
        from core.seed import seed_default_tables

        with transaction.atomic():
            # Delete dependent rows first (in order of dependencies)
            cart_del = Cart.objects.all().delete()[0]
            order_del = Order.objects.all().delete()[0]
            res_del = Reservation.objects.all().delete()[0]
            hold_del = ReservationHold.objects.all().delete()[0]
            tbl_del = Table.objects.all().delete()[0]

        created = seed_default_tables(min_tables=count)

        self.stdout.write(self.style.SUCCESS(
            f"Reset complete. Deleted: carts={cart_del}, orders={order_del}, reservations={res_del}, holds={hold_del}, tables={tbl_del}. "
            f"Seeded: org+{created['organizations']}, loc+{created['locations']}, tables+{created['tables']}"
        ))

