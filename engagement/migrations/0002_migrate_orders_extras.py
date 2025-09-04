from __future__ import annotations

from django.db import migrations, connection, ProgrammingError


def _table_names() -> set[str]:
    try:
        return set(connection.introspection.table_names())
    except Exception:
        # Fallback for unusual backends
        with connection.cursor() as cursor:
            try:
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                return {row[0] for row in cursor.fetchall()}
            except Exception:
                return set()


def copy_legacy_orders_extras(apps, schema_editor):
    """
    Copies rows from any legacy orders_extras table into engagement_orderextras.
    No-op if legacy table is absent or target already has rows.
    """
    candidates = [
        "orders_extras_orderextra",
        "orders_extras_orderextras",
    ]
    tables = _table_names()
    old = next((t for t in candidates if t in tables), None)
    if not old:
        return

    with connection.cursor() as cursor:
        # Skip if target already populated
        cursor.execute("SELECT COUNT(1) FROM engagement_orderextras")
        if (cursor.fetchone() or [0])[0] > 0:
            return

        # Detect available columns on legacy table
        cols = set()
        try:
            for d in connection.introspection.get_table_description(cursor, old):
                cols.add(d.name)
        except Exception:
            # Best-effort fallback for SQLite
            try:
                cursor.execute(f"PRAGMA table_info({old})")
                for row in cursor.fetchall():
                    cols.add(row[1])
            except Exception:
                cols = set()

        has_meta = "meta" in cols
        has_created = "created_at" in cols
        select_meta = "meta" if has_meta else "NULL"
        select_created = "created_at" if has_created else "CURRENT_TIMESTAMP"

        sql = (
            "INSERT INTO engagement_orderextras (id, order_id, name, amount, meta, created_at)\n"
            f"SELECT id, order_id, COALESCE(name, ''), COALESCE(amount, 0), {select_meta}, {select_created} "
            f"FROM {old}"
        )

        try:
            # Prefer idempotent insert when supported
            cursor.execute(sql + " ON CONFLICT(id) DO NOTHING")
        except ProgrammingError:
            # Portable fallback
            cursor.execute(
                "INSERT INTO engagement_orderextras (id, order_id, name, amount, meta, created_at)\n"
                f"SELECT o.id, o.order_id, COALESCE(o.name, ''), COALESCE(o.amount, 0), {select_meta}, {select_created} "
                f"FROM {old} o\n"
                "WHERE NOT EXISTS (SELECT 1 FROM engagement_orderextras e WHERE e.id = o.id)"
            )


class Migration(migrations.Migration):

    dependencies = [
        ("engagement", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(copy_legacy_orders_extras, migrations.RunPython.noop),
    ]

