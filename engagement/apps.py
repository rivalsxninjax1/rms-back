from django.apps import AppConfig
from django.conf import settings

class EngagementConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "engagement"
    verbose_name = "Engagement (Tips, Loyalty, Holds)"

    def ready(self):
        # Attach a convenience property on Order so code can do: order.tip_amount
        # without modifying the orders app.
        try:
            from orders.models import Order
            from .models import OrderExtras
            from decimal import Decimal

            def _tip_amount(self) -> "Decimal":
                try:
                    ox = OrderExtras.objects.select_related("order").get(order_id=self.id)
                    return ox.tip_amount
                except OrderExtras.DoesNotExist:
                    return Decimal("0.00")

            if not hasattr(Order, "tip_amount"):
                Order.tip_amount = property(_tip_amount)
        except Exception:
            # Avoid import issues during migrations
            pass
