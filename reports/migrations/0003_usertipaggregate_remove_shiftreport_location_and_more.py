# FILE: reports/migrations/0003_usertipaggregate_remove_shiftreport_location_and_more.py
from django.db import migrations

DROP_VIEW_SQL = "DROP VIEW IF EXISTS reports_user_tip_agg;"

CREATE_VIEW_SQL = """
CREATE VIEW IF NOT EXISTS reports_user_tip_agg AS
SELECT
    oe.user_id                    AS user_id,
    COALESCE(SUM(oe.tip_amount), 0) AS total_tip
FROM orders_extras_orderextra AS oe
GROUP BY oe.user_id;
"""

class Migration(migrations.Migration):

    # Make sure we still run after the view was introduced,
    # and after the orders_extras base table exists.
    dependencies = [
        ("reports", "0002_user_tips_view"),
        ("orders_extras", "0001_initial"),
    ]
    DROP_VIEW_SQL = "DROP VIEW IF EXISTS reports_user_tip_agg;"

    operations = [
        # 1) Drop the view so SQLite can freely alter/rename tables in this migration.
        migrations.RunSQL(sql=DROP_VIEW_SQL, reverse_sql=""),
        
        # 2) >>> If your original 0003 had model/field operations,
        #       paste them here between the two RunSQL operations. Example:
        # migrations.RemoveField(...),
        # migrations.AddField(...),
        # migrations.AlterField(...),
        # ... (whatever your original 0003 contained) ...
        #
        # If you don’t have any other ops, leave this section empty.

        # 3) Recreate the view after all structural changes are complete.
        migrations.RunSQL(sql=CREATE_VIEW_SQL, reverse_sql=DROP_VIEW_SQL),
    ]








