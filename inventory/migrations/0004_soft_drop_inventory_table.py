from django.db import migrations


def rename_table_if_exists(apps, schema_editor):
    """Rename table only if it exists"""
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='inventory_table';"
        )
        if cursor.fetchone():
            cursor.execute("ALTER TABLE inventory_table RENAME TO inventory_table_legacy;")


def reverse_rename_table(apps, schema_editor):
    """Reverse the rename operation"""
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='inventory_table_legacy';"
        )
        if cursor.fetchone():
            cursor.execute("ALTER TABLE inventory_table_legacy RENAME TO inventory_table;")


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0003_link_core_table"),
    ]

    operations = [
        # Soft-drop: rename legacy table, preserving data and allowing rollback.
        migrations.RunPython(
            rename_table_if_exists,
            reverse_rename_table,
        )
    ]

