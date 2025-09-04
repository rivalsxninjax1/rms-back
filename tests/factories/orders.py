import factory
from decimal import Decimal

from orders import models as order_models
from .accounts import UserFactory


class OrderFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = order_models.Order

    user = factory.SubFactory(UserFactory)
    status = order_models.Order.STATUS_PENDING
    delivery_option = "PICKUP"

    # Monetary fields kept minimal, relying on model defaults and checks
    subtotal = Decimal("0.00")
    modifier_total = Decimal("0.00")
    discount_amount = Decimal("0.00")
    coupon_discount = Decimal("0.00")
    loyalty_discount = Decimal("0.00")
    tip_amount = Decimal("0.00")
    delivery_fee = Decimal("0.00")
    service_fee = Decimal("0.00")
    tax_amount = Decimal("0.00")
    tax_rate = Decimal("0.0000")
    total_amount = Decimal("0.00")
    payment_status = "PENDING"

