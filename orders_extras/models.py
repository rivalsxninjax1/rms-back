from __future__ import annotations

from django.db import models


class OrderExtra(models.Model):
    """
    Minimal placeholder so any old imports like `from orders_extras.models import OrderExtra`
    won't crash. We mark this as managed=False so migrations won't try to create a table.
    """
    id = models.BigAutoField(primary_key=True)

    class Meta:
        app_label = "orders_extras"
        managed = False
        db_table = "orders_extras_orderextra"  # arbitrary; never created since managed=False

    def __str__(self) -> str:
        return f"OrderExtra#{self.pk}"
