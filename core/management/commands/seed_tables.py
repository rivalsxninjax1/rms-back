from __future__ import annotations

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Seed default organization, location, and a set of tables if none exist."

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=6, help="Minimum number of tables to seed (default: 6)")

    def handle(self, *args, **options):
        count = options["count"]
        from core.seed import seed_default_tables
        created = seed_default_tables(min_tables=count)
        self.stdout.write(self.style.SUCCESS(
            f"Seed complete: org+{created['organizations']}, loc+{created['locations']}, tables+{created['tables']}"
        ))

