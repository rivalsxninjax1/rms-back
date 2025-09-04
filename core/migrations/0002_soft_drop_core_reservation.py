from django.db import migrations


def rename_core_reservation_if_exists(apps, schema_editor):
    """Rename core_reservation table only if it exists"""
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='core_reservation';"
        )
        if cursor.fetchone():
            cursor.execute("ALTER TABLE core_reservation RENAME TO core_reservation_legacy;")


def reverse_rename_core_reservation(apps, schema_editor):
    """Reverse the rename operation"""
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='core_reservation_legacy';"
        )
        if cursor.fetchone():
            cursor.execute("ALTER TABLE core_reservation_legacy RENAME TO core_reservation;")


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
        ("reservations", "0005_migrate_from_core"),
    ]

    operations = [
        # Soft-drop: rename the legacy table so the canonical app owns the name.
        # Reversible by renaming back.
        migrations.RunPython(
            rename_core_reservation_if_exists,
            reverse_rename_core_reservation,
        ),
    ]

