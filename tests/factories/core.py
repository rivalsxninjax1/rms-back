import factory
from decimal import Decimal

from core import models as core_models


class OrganizationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = core_models.Organization

    name = factory.Sequence(lambda n: f"Org {n}")
    tax_percent = Decimal("0.00")
    address = ""
    phone = ""
    email = ""


class LocationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = core_models.Location

    organization = factory.SubFactory(OrganizationFactory)
    name = factory.Sequence(lambda n: f"Location {n}")
    address = ""
    timezone = "UTC"
    is_active = True

