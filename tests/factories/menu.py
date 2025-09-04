import factory
from decimal import Decimal

from menu import models as menu_models
from .core import OrganizationFactory


class MenuCategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = menu_models.MenuCategory

    organization = factory.SubFactory(OrganizationFactory)
    name = factory.Sequence(lambda n: f"Category {n}")
    slug = factory.LazyAttribute(lambda o: f"category-{o.name.split()[-1].lower()}")
    description = ""
    is_active = True
    sort_order = 0


class MenuItemFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = menu_models.MenuItem

    organization = factory.SelfAttribute("category.organization")
    category = factory.SubFactory(MenuCategoryFactory)
    name = factory.Sequence(lambda n: f"Item {n}")
    slug = factory.LazyAttribute(lambda o: f"item-{o.name.split()[-1].lower()}")
    description = ""
    short_description = ""
    price = Decimal("9.99")
    is_available = True
    is_featured = False
    is_popular = False
    is_new = False


class ModifierGroupFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = menu_models.ModifierGroup

    menu_item = factory.SubFactory(MenuItemFactory)
    name = factory.Sequence(lambda n: f"Group {n}")
    is_required = False
    min_select = 0
    max_select = 3
    sort_order = 0


class ModifierFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = menu_models.Modifier

    modifier_group = factory.SubFactory(ModifierGroupFactory)
    name = factory.Sequence(lambda n: f"Mod {n}")
    price = Decimal("1.00")
    is_available = True
    sort_order = 0
