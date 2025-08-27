# FILE: reports/migrations/0002_user_tips_view.py
from django.db import migrations

CREATE_VIEW_SQL = """
CREATE VIEW IF NOT EXISTS reports_user_tip_agg AS
SELECT
    oe.user_id                    AS user_id,
    COALESCE(SUM(oe.tip_amount), 0) AS total_tip
FROM orders_extras_orderextra AS oe
GROUP BY oe.user_id;
"""

DROP_VIEW_SQL = "DROP VIEW IF EXISTS reports_user_tip_agg;"

class Migration(migrations.Migration):

    dependencies = [
        ("reports", "0001_initial"),
        # Ensure the base table exists before creating the view
        ("orders_extras", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(sql=CREATE_VIEW_SQL, reverse_sql=DROP_VIEW_SQL),
    ]
