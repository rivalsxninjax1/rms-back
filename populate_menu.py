#!/usr/bin/env python3

import os
import sys
import django
from decimal import Decimal

# Add the project directory to Python path
sys.path.append('/Users/sickboi/Desktop/rms-back')

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rms_backend.settings.development')
django.setup()

# Now import Django models
from core.models import Organization
from menu.models import MenuCategory, MenuItem, ModifierGroup, Modifier

def create_sample_data():
    print("Creating sample menu data...")
    
    # Create or get organization
    organization, created = Organization.objects.get_or_create(
        name="Sample Restaurant",
        defaults={
            'tax_percent': Decimal('8.25'),
            'address': '123 Main St, City, State 12345',
            'phone': '+1-555-123-4567',
            'email': 'info@samplerestaurant.com'
        }
    )
    if created:
        print(f"Created organization: {organization.name}")
    else:
        print(f"Using existing organization: {organization.name}")
    
    # Create categories
    categories_data = [
        {
            'name': 'Appetizers',
            'description': 'Start your meal with our delicious appetizers',
            'is_featured': True
        },
        {
            'name': 'Main Courses',
            'description': 'Hearty main dishes to satisfy your appetite',
            'is_featured': True
        },
        {
            'name': 'Desserts',
            'description': 'Sweet treats to end your meal perfectly',
            'is_featured': False
        },
        {
            'name': 'Beverages',
            'description': 'Refreshing drinks and specialty beverages',
            'is_featured': False
        }
    ]
    
    categories = {}
    for cat_data in categories_data:
        category, created = MenuCategory.objects.get_or_create(
            organization=organization,
            name=cat_data['name'],
            defaults={
                'description': cat_data['description'],
                'is_featured': cat_data['is_featured'],
                'is_active': True
            }
        )
        categories[cat_data['name']] = category
        if created:
            print(f"Created category: {category.name}")
        else:
            print(f"Category already exists: {category.name}")
    
    # Create menu items
    menu_items_data = [
        # Appetizers
        {
            'category': 'Appetizers',
            'name': 'Buffalo Wings',
            'description': 'Crispy chicken wings tossed in spicy buffalo sauce, served with celery and blue cheese dip',
            'price': Decimal('12.99'),
            'is_featured': True,
            'is_popular': True
        },
        {
            'category': 'Appetizers',
            'name': 'Mozzarella Sticks',
            'description': 'Golden fried mozzarella cheese sticks served with marinara sauce',
            'price': Decimal('8.99'),
            'is_vegetarian': True
        },
        {
            'category': 'Appetizers',
            'name': 'Loaded Nachos',
            'description': 'Crispy tortilla chips topped with cheese, jalapeños, sour cream, and guacamole',
            'price': Decimal('10.99'),
            'is_vegetarian': True
        },
        
        # Main Courses
        {
            'category': 'Main Courses',
            'name': 'Classic Burger',
            'description': 'Juicy beef patty with lettuce, tomato, onion, and pickles on a brioche bun',
            'price': Decimal('14.99'),
            'is_featured': True,
            'is_popular': True
        },
        {
            'category': 'Main Courses',
            'name': 'Grilled Chicken Caesar Salad',
            'description': 'Fresh romaine lettuce with grilled chicken, parmesan cheese, croutons, and caesar dressing',
            'price': Decimal('13.99'),
            'is_popular': True
        },
        {
            'category': 'Main Courses',
            'name': 'Margherita Pizza',
            'description': 'Fresh mozzarella, tomato sauce, and basil on our homemade pizza dough',
            'price': Decimal('16.99'),
            'is_vegetarian': True,
            'is_featured': True
        },
        {
            'category': 'Main Courses',
            'name': 'Fish and Chips',
            'description': 'Beer-battered cod served with crispy fries and tartar sauce',
            'price': Decimal('17.99')
        },
        
        # Desserts
        {
            'category': 'Desserts',
            'name': 'Chocolate Brownie Sundae',
            'description': 'Warm chocolate brownie topped with vanilla ice cream, chocolate sauce, and whipped cream',
            'price': Decimal('7.99'),
            'is_vegetarian': True
        },
        {
            'category': 'Desserts',
            'name': 'New York Cheesecake',
            'description': 'Rich and creamy cheesecake with graham cracker crust and berry compote',
            'price': Decimal('6.99'),
            'is_vegetarian': True
        },
        
        # Beverages
        {
            'category': 'Beverages',
            'name': 'Craft Beer Selection',
            'description': 'Ask your server about our rotating selection of local craft beers',
            'price': Decimal('5.99')
        },
        {
            'category': 'Beverages',
            'name': 'Fresh Lemonade',
            'description': 'House-made lemonade with fresh lemons and mint',
            'price': Decimal('3.99'),
            'is_vegetarian': True,
            'is_vegan': True
        },
        {
            'category': 'Beverages',
            'name': 'Coffee',
            'description': 'Freshly brewed coffee, regular or decaf',
            'price': Decimal('2.99'),
            'is_vegetarian': True,
            'is_vegan': True
        }
    ]
    
    menu_items = {}
    for item_data in menu_items_data:
        category = categories[item_data['category']]
        item, created = MenuItem.objects.get_or_create(
            organization=organization,
            category=category,
            name=item_data['name'],
            defaults={
                'description': item_data['description'],
                'price': item_data['price'],
                'is_available': True,
                'is_featured': item_data.get('is_featured', False),
                'is_popular': item_data.get('is_popular', False),
                'is_vegetarian': item_data.get('is_vegetarian', False),
                'is_vegan': item_data.get('is_vegan', False),
                'preparation_time': 15
            }
        )
        menu_items[item_data['name']] = item
        if created:
            print(f"Created menu item: {item.name} - ${item.price}")
        else:
            print(f"Menu item already exists: {item.name}")
    
    print(f"\nSample data creation completed!")
    print(f"Organization: {organization.name}")
    print(f"Categories: {len(categories)}")
    print(f"Menu Items: {len(menu_items)}")
    print("\nYou can now view the menu items in the admin panel or through the API.")

if __name__ == '__main__':
    create_sample_data()