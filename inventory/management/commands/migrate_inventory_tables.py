from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.models import Table as CoreTable
from inventory.models import Table as InventoryTable, TableAsset


class Command(BaseCommand):
    help = "Migrate inventory.Table asset fields into TableAsset linked to core.Table (dry-run by default)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Perform writes. Without this, runs as dry-run.")
        parser.add_argument("--limit", type=int, default=0, help="Limit rows for testing")

    def handle(self, *args, **options):
        apply = options["apply"]
        limit = options["limit"]

        qs = InventoryTable.objects.select_related("location").all().order_by("pk")
        if limit:
            qs = qs[:limit]

        created_assets = 0
        linked_existing = 0
        created_tables = 0
        skipped = 0

        for inv in qs:
            # Match core.Table by (location, table_number)
            core = CoreTable.objects.filter(location=inv.location, table_number=inv.table_number).first()
            if not core and apply:
                core = CoreTable.objects.create(
                    location=inv.location,
                    table_number=inv.table_number,
                    capacity=inv.capacity,
                    is_active=inv.is_active,
                    table_type="dining",
                )
                created_tables += 1

            if not core:
                self.stdout.write(self.style.WARNING(f"No core.Table for inventory.Table id={inv.id}; would create on --apply"))
                skipped += 1
                continue

            if hasattr(core, "asset") and core.asset:
                linked_existing += 1
                continue

            if apply:
                TableAsset.objects.create(
                    table=core,
                    condition=inv.condition,
                    last_maintenance=inv.last_maintenance,
                    purchase_date=inv.purchase_date,
                    purchase_cost=inv.purchase_cost,
                )
                created_assets += 1
            else:
                created_assets += 1  # count as potential

        self.stdout.write(self.style.SUCCESS(
            f"Completed. potential/new assets={created_assets}, existing-linked={linked_existing}, new core tables={created_tables}, skipped={skipped}"
        ))
