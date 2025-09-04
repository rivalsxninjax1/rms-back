from __future__ import annotations

from django.db import transaction


def seed_default_tables(min_tables: int = 6) -> dict:
    """
    Idempotently seed Organization, Location and a handful of Tables if none exist.
    Returns a summary dict with counts created.
    """
    from core.models import Organization, Location, Table

    created = {"organizations": 0, "locations": 0, "tables": 0}

    with transaction.atomic():
        if Table.objects.exists():
            return created

        org, org_created = Organization.objects.get_or_create(name="Default Organization")
        if org_created:
            created["organizations"] += 1
        loc, loc_created = Location.objects.get_or_create(organization=org, name="Main")
        if loc_created:
            created["locations"] += 1

        # Consistent naming: T1..T<n>
        for num in range(1, min_tables + 1):
            _, t_created = Table.objects.get_or_create(
                location=loc,
                table_number=f"T{num}",
                defaults={"capacity": 4, "is_active": True, "table_type": "dining"},
            )
            if t_created:
                created["tables"] += 1

    return created
