from core.models import Organization
from menu.models import MenuCategory, MenuItem
from decimal import Decimal

# Create organization
org, created = Organization.objects.get_or_create(
    name="Sample Restaurant",
    defaults={
        "tax_percent": Decimal("8.25"),
        "address": "123 Main St",
        "phone": "+15551234567",
        "email": "info@sample.com"
    }
)
print(f"Organization: {org.name}")

# Create categories
appetizers, _ = MenuCategory.objects.get_or_create(
    organization=org,
    name="Appetizers",
    defaults={"description": "Delicious appetizers", "is_active": True}
)

mains, _ = MenuCategory.objects.get_or_create(
    organization=org,
    name="Main Courses",
    defaults={"description": "Hearty main dishes", "is_active": True}
)

print(f"Categories created: {appetizers.name}, {mains.name}")

# Create menu items
appetizer_item, created = MenuItem.objects.get_or_create(
    name="Buffalo Wings",
    organization=org,
    defaults={
        'description': "Spicy buffalo wings served with ranch dressing",
        'price': Decimal('12.99'),
        'category': appetizers,
        'is_available': True
    }
)

main_item, created = MenuItem.objects.get_or_create(
    name="Classic Burger",
    organization=org,
    defaults={
        'description': "Juicy beef patty with lettuce, tomato, and cheese",
        'price': Decimal('15.99'),
        'category': mains,
        'is_available': True
    }
)

print(f"Created organization: {org.name}")
print(f"Created categories: {appetizers.name}, {mains.name}")
print(f"Created menu items: {appetizer_item.name}, {main_item.name}")
print("Menu setup completed successfully!")
