from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class UserTipAggregate(models.Model):
    """
    Managed=False model backed by a DB VIEW (see migration 0002).
    Columns:
      user_id, username, rank, total_tip, avg_tip, max_tip, last_tip_date
    """
    user = models.OneToOneField(User, primary_key=True, on_delete=models.DO_NOTHING, related_name="tip_aggregate")
    username = models.CharField(max_length=150)
    rank = models.CharField(max_length=16)
    total_tip = models.DecimalField(max_digits=12, decimal_places=2)
    avg_tip = models.DecimalField(max_digits=12, decimal_places=2)
    max_tip = models.DecimalField(max_digits=12, decimal_places=2)
    last_tip_date = models.DateField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "reports_user_tip_agg"
        verbose_name = "User Tips (Aggregate)"
        verbose_name_plural = "User Tips (Aggregate)"
