from __future__ import annotations

from decimal import Decimal
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from orders.models import Order
from payments.post_payment import order_paid
from .models import DailySales, ShiftReport, AuditLog


def _q2(x) -> Decimal:
    try:
        return Decimal(str(x or 0)).quantize(Decimal("0.01"))
    except Exception:
        return Decimal("0.00")


def _broadcast(topic: str, data: dict) -> None:
    try:
        layer = get_channel_layer()
        if not layer:
            return
        async_to_sync(layer.group_send)(
            "reports",
            {"type": "broadcast", "data": {"topic": topic, "data": data}},
        )
    except Exception:
        # Best-effort only
        pass


@receiver(order_paid)
def on_order_paid_update_daily_sales(sender, order=None, payment=None, request=None, **kwargs):
    """
    When an order is paid, recalc today's DailySales and broadcast an update.
    """
    try:
        today = timezone.localdate()
        # Consider orders completed today; fallback to created_at if no completed_at
        orders = Order.objects.filter(
            created_at__date=today
        ).exclude(status=Order.STATUS_CANCELLED)

        total_orders = orders.count()
        # Sum numeric fields defensively
        subtotal = sum((Decimal(str(getattr(o, "subtotal", 0) or 0)) for o in orders), Decimal("0"))
        tips = sum((Decimal(str(getattr(o, "tip_amount", 0) or 0)) for o in orders), Decimal("0"))
        discounts = sum(
            (
                Decimal(str(getattr(o, "discount_amount", 0) or 0))
                + Decimal(str(getattr(o, "coupon_discount", 0) or 0))
                + Decimal(str(getattr(o, "loyalty_discount", 0) or 0))
            )
            for o in orders
        )
        total = sum((Decimal(str(getattr(o, "total_amount", 0) or 0)) for o in orders), Decimal("0"))

        obj, _ = DailySales.objects.get_or_create(date=today)
        obj.total_orders = total_orders
        obj.subtotal_cents = int((_q2(subtotal) * 100).to_integral_value())
        obj.tip_cents = int((_q2(tips) * 100).to_integral_value())
        obj.discount_cents = int((_q2(discounts) * 100).to_integral_value())
        obj.total_cents = int((_q2(total) * 100).to_integral_value())
        obj.save(update_fields=[
            "total_orders", "subtotal_cents", "tip_cents", "discount_cents", "total_cents"
        ])

        _broadcast("daily_sales", {
            "date": str(today),
            "total_orders": obj.total_orders,
            "subtotal_cents": obj.subtotal_cents,
            "tip_cents": obj.tip_cents,
            "discount_cents": obj.discount_cents,
            "total_cents": obj.total_cents,
        })
    except Exception:
        # Non-fatal
        pass


@receiver(post_save, sender=ShiftReport)
def on_shift_report_saved(sender, instance: ShiftReport, created: bool, **kwargs):
    data = {
        "id": instance.id,
        "date": str(instance.date),
        "shift": instance.shift,
        "staff": instance.staff,
        "orders_count": instance.orders_count,
        "total_cents": instance.total_cents,
        "opened_at": instance.opened_at.isoformat() if instance.opened_at else None,
        "closed_at": instance.closed_at.isoformat() if instance.closed_at else None,
        "over_short_cents": instance.over_short_cents,
    }
    _broadcast("shift_report", data)


@receiver(post_save, sender=AuditLog)
def on_audit_log_saved(sender, instance: AuditLog, created: bool, **kwargs):
    if not created:
        return
    data = {
        "id": instance.id,
        "action": instance.action,
        "description": instance.description,
        "model": instance.model_name,
        "object_id": instance.object_id,
        "user": getattr(instance.user, "username", None),
        "created_at": instance.created_at.isoformat(),
        "category": instance.category,
        "severity": instance.severity,
    }
    _broadcast("audit_log", data)

