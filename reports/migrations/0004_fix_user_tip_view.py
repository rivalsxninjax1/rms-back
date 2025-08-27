# FILE: reports/migrations/0004_fix_user_tip_view.py
from django.db import migrations

DROP_VIEW_SQL = """
DROP VIEW IF EXISTS reports_user_tip_agg;
"""

# We sum tips taking OrderExtras.tip_amount when present, else Order.tip_amount.
# We also aggregate by an identity column (user_id if present else created_by_id).
CREATE_VIEW_SQL = """
CREATE VIEW reports_user_tip_agg AS
SELECT
    COALESCE(o.user_id, o.created_by_id) AS user_id,
    SUM(
        COALESCE(ox.tip_amount, o.tip_amount, 0)
    ) AS total_tip,
    COUNT(1) AS orders_count
FROM orders_order o
LEFT JOIN orders_extras_orderextra ox
    ON ox.order_id = o.id
-- Only count paid/completed orders if your schema uses these flags.
-- If you don't have these columns, the conditions just evaluate to NULL (ignored).
WHERE
    COALESCE(
        CASE WHEN o.status = 'PAID' THEN 1 ELSE NULL END,
        CASE WHEN o.is_paid = 1 THEN 1 ELSE NULL END,
        1
    ) IS NOT NULL
GROUP BY COALESCE(o.user_id, o.created_by_id);
"""

class Migration(migrations.Migration):

    # IMPORTANT: make sure this migration runs AFTER orders_extras has created its table.
    dependencies = [
        ("reports", "0003_usertipaggregate_remove_shiftreport_location_and_more"),
        ("orders_extras", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(DROP_VIEW_SQL, reverse_sql=DROP_VIEW_SQL),
        migrations.RunSQL(CREATE_VIEW_SQL, reverse_sql=DROP_VIEW_SQL),
    ]
