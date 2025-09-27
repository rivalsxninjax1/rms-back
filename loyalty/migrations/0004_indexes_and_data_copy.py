from __future__ import annotations

from django.db import migrations, models, connection, ProgrammingError


def _table_exists(cursor, table_name: str) -> bool:
    try:
        cursor.execute("SELECT 1 FROM %s WHERE 1=0" % table_name)  # naive check; will fail if missing
        return True
    except Exception:
        return False


def copy_from_loyalty_tables_to_loyality(apps, schema_editor):
    """
    Safety net: if previous runs created tables with the prefix 'loyalty_' instead of
    the historical 'loyality_', copy rows into the canonical tables if needed.
    No-op when canonical tables already contain data.
    """
    with connection.cursor() as cursor:
        # Rank
        if _table_exists(cursor, 'loyalty_loyaltyrank') and _table_exists(cursor, 'loyality_loyaltyrank'):
            try:
                cursor.execute("SELECT COUNT(1) FROM loyality_loyaltyrank")
                count_target = cursor.fetchone()[0]
                if count_target == 0:
                    cursor.execute(
                        """
                        INSERT INTO loyality_loyaltyrank (id, code, name, tip_cents, is_active, sort_order, earn_points_per_currency, burn_cents_per_point)
                        SELECT id, code, name, tip_cents, is_active, sort_order,
                               COALESCE(earn_points_per_currency, 1.00), COALESCE(burn_cents_per_point, 1)
                        FROM loyalty_loyaltyrank
                        ON CONFLICT(id) DO NOTHING
                        """
                    )
            except ProgrammingError:
                # Fallback for DBs without ON CONFLICT
                cursor.execute(
                    """
                    INSERT INTO loyality_loyaltyrank (id, code, name, tip_cents, is_active, sort_order, earn_points_per_currency, burn_cents_per_point)
                    SELECT lr.id, lr.code, lr.name, lr.tip_cents, lr.is_active, lr.sort_order,
                           COALESCE(lr.earn_points_per_currency, 1.00), COALESCE(lr.burn_cents_per_point, 1)
                    FROM loyalty_loyaltyrank lr
                    WHERE NOT EXISTS (SELECT 1 FROM loyality_loyaltyrank l2 WHERE l2.id = lr.id)
                    """
                )

        # Profile
        if _table_exists(cursor, 'loyalty_loyaltyprofile') and _table_exists(cursor, 'loyality_loyaltyprofile'):
            try:
                cursor.execute("SELECT COUNT(1) FROM loyality_loyaltyprofile")
                count_target = cursor.fetchone()[0]
                if count_target == 0:
                    cursor.execute(
                        """
                        INSERT INTO loyality_loyaltyprofile (id, user_id, rank_id, notes, points)
                        SELECT id, user_id, rank_id, COALESCE(notes, ''), COALESCE(points, 0)
                        FROM loyalty_loyaltyprofile
                        ON CONFLICT(id) DO NOTHING
                        """
                    )
            except ProgrammingError:
                cursor.execute(
                    """
                    INSERT INTO loyality_loyaltyprofile (id, user_id, rank_id, notes, points)
                    SELECT lp.id, lp.user_id, lp.rank_id, COALESCE(lp.notes, ''), COALESCE(lp.points, 0)
                    FROM loyalty_loyaltyprofile lp
                    WHERE NOT EXISTS (SELECT 1 FROM loyality_loyaltyprofile l2 WHERE l2.id = lp.id)
                    """
                )

        # Ledger
        if _table_exists(cursor, 'loyalty_loyaltypointsledger') and _table_exists(cursor, 'loyality_loyaltypointsledger'):
            try:
                cursor.execute("SELECT COUNT(1) FROM loyality_loyaltypointsledger")
                count_target = cursor.fetchone()[0]
                if count_target == 0:
                    cursor.execute(
                        """
                        INSERT INTO loyality_loyaltypointsledger (id, profile_id, delta, type, reason, reference, created_by_id, created_at)
                        SELECT id, profile_id, delta, type, COALESCE(reason, ''), COALESCE(reference, ''), created_by_id, created_at
                        FROM loyalty_loyaltypointsledger
                        ON CONFLICT(id) DO NOTHING
                        """
                    )
            except ProgrammingError:
                cursor.execute(
                    """
                    INSERT INTO loyality_loyaltypointsledger (id, profile_id, delta, type, reason, reference, created_by_id, created_at)
                    SELECT ll.id, ll.profile_id, ll.delta, ll.type, COALESCE(ll.reason, ''), COALESCE(ll.reference, ''), ll.created_by_id, ll.created_at
                    FROM loyalty_loyaltypointsledger ll
                    WHERE NOT EXISTS (SELECT 1 FROM loyality_loyaltypointsledger l2 WHERE l2.id = ll.id)
                    """
                )


class Migration(migrations.Migration):

    dependencies = [
        ("loyality", "0003_loyaltypointsledger_loyality_lo_profile_255165_idx_and_more"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="loyaltypointsledger",
            index=models.Index(fields=["profile", "-created_at"], name="ll_profile_created_idx"),
        ),
        migrations.AddIndex(
            model_name="loyaltypointsledger",
            index=models.Index(fields=["type", "-created_at"], name="ll_type_created_idx"),
        ),
        migrations.RunPython(copy_from_loyalty_tables_to_loyality, migrations.RunPython.noop),
    ]

