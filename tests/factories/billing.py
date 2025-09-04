import factory
from decimal import Decimal

from billing import models as billing_models
from .orders import OrderFactory


class PaymentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = billing_models.Payment

    order = factory.SubFactory(OrderFactory)
    amount = Decimal("9.99")
    currency = "NPR"
    status = "created"
    reference = ""

