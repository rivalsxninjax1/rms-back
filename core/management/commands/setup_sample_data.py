from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from decimal import Decimal
from core.models import Organization, Location
from menu.models import MenuCategory, MenuItem
from reservations.models import Table
from coupons.models import Coupon
from orders.models import TipTier, DiscountRule

User = get_user_model()


class Command(BaseCommand):
    help = 'Create sample data for testing the restaurant management system'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Setting up sample data...'))

        # Create organization and location
        org, created = Organization.objects.get_or_create(
            name="Sample Restaurant",
            defaults={
                'tax_percent': Decimal('8.5'),
                'address': '123 Main St, City, State 12345',
                'phone': '+1234567890',
                'email': 'contact@samplerestaurant.com'
            }
        )
        
        location, created = Location.objects.get_or_create(
            organization=org,
            name="Main Location",
            defaults={
                'address': '123 Main St, City, State 12345',
                'timezone': 'America/New_York',
                'is_active': True
            }
        )

        # Create sample menu categories
        categories_data = [
            {'name': 'Appetizers', 'description': 'Start your meal with our delicious appetizers'},
            {'name': 'Main Courses', 'description': 'Hearty main dishes to satisfy your appetite'},
            {'name': 'Desserts', 'description': 'Sweet treats to end your meal'},
            {'name': 'Beverages', 'description': 'Refreshing drinks and hot beverages'},
        ]

        categories = {}
        for i, cat_data in enumerate(categories_data):
            cat, created = MenuCategory.objects.get_or_create(
                organization=org,
                name=cat_data['name'],
                defaults={
                    'description': cat_data['description'],
                    'sort_order': i,
                    'is_active': True
                }
            )
            categories[cat_data['name']] = cat

        # Create sample menu items
        menu_items_data = [
            # Appetizers
            {'category': 'Appetizers', 'name': 'Caesar Salad', 'description': 'Fresh romaine lettuce with caesar dressing', 'price': '12.99'},
            {'category': 'Appetizers', 'name': 'Buffalo Wings', 'description': 'Spicy chicken wings with blue cheese', 'price': '14.99'},
            {'category': 'Appetizers', 'name': 'Mozzarella Sticks', 'description': 'Crispy fried mozzarella with marinara sauce', 'price': '9.99'},
            
            # Main Courses
            {'category': 'Main Courses', 'name': 'Margherita Pizza', 'description': 'Classic pizza with tomato, mozzarella, and basil', 'price': '18.99', 'is_vegetarian': True},
            {'category': 'Main Courses', 'name': 'Grilled Salmon', 'description': 'Fresh Atlantic salmon with lemon butter sauce', 'price': '26.99'},
            {'category': 'Main Courses', 'name': 'Ribeye Steak', 'description': '12oz ribeye steak cooked to perfection', 'price': '32.99'},
            {'category': 'Main Courses', 'name': 'Chicken Parmesan', 'description': 'Breaded chicken breast with marinara and mozzarella', 'price': '22.99'},
            
            # Desserts
            {'category': 'Desserts', 'name': 'Chocolate Cake', 'description': 'Rich chocolate cake with chocolate frosting', 'price': '8.99'},
            {'category': 'Desserts', 'name': 'Tiramisu', 'description': 'Classic Italian dessert with coffee and mascarpone', 'price': '9.99'},
            
            # Beverages
            {'category': 'Beverages', 'name': 'Coffee', 'description': 'Freshly brewed coffee', 'price': '3.99'},
            {'category': 'Beverages', 'name': 'Fresh Orange Juice', 'description': 'Freshly squeezed orange juice', 'price': '4.99'},
            {'category': 'Beverages', 'name': 'Coca-Cola', 'description': 'Classic soft drink', 'price': '2.99'},
        ]

        for i, item_data in enumerate(menu_items_data):
            MenuItem.objects.get_or_create(
                organization=org,
                category=categories[item_data['category']],
                name=item_data['name'],
                defaults={
                    'description': item_data['description'],
                    'price': Decimal(item_data['price']),
                    'is_vegetarian': item_data.get('is_vegetarian', False),
                    'is_available': True,
                    'preparation_time': 15,
                    'sort_order': i
                }
            )

        # Create sample tables
        table_data = [
            {'table_number': '1', 'capacity': 2},
            {'table_number': '2', 'capacity': 4},
            {'table_number': '3', 'capacity': 6},
            {'table_number': '4', 'capacity': 2},
            {'table_number': '5', 'capacity': 4},
            {'table_number': '6', 'capacity': 8},
        ]

        for table_info in table_data:
            Table.objects.get_or_create(
                location=location,
                table_number=table_info['table_number'],
                defaults={
                    'capacity': table_info['capacity'],
                    'is_active': True
                }
            )

        # Create sample coupons
        coupon_data = [
            {'code': 'WELCOME10', 'percent': 10, 'phrase': 'Welcome discount - 10% off'},
            {'code': 'SAVE15', 'percent': 15, 'phrase': 'Save 15% on your order'},
            {'code': 'NEWUSER20', 'percent': 20, 'phrase': 'New user special - 20% off'},
        ]

        for coupon_info in coupon_data:
            Coupon.objects.get_or_create(
                code=coupon_info['code'],
                defaults={
                    'percent': coupon_info['percent'],
                    'phrase': coupon_info['phrase'],
                    'active': True,
                    'max_uses': 100,
                    'times_used': 0
                }
            )

        # Create tip tiers
        tip_tiers_data = [
            {'rank': 'BRONZE', 'default_tip_amount': Decimal('2.00')},
            {'rank': 'SILVER', 'default_tip_amount': Decimal('3.00')},
            {'rank': 'GOLD', 'default_tip_amount': Decimal('5.00')},
            {'rank': 'PLATINUM', 'default_tip_amount': Decimal('7.00')},
        ]

        for tier_info in tip_tiers_data:
            TipTier.objects.get_or_create(
                rank=tier_info['rank'],
                defaults={
                    'default_tip_amount': tier_info['default_tip_amount']
                }
            )

        # Create discount rules
        discount_rules_data = [
            {'threshold_cents': 2000, 'discount_cents': 100},  # $20 order gets $1 off
            {'threshold_cents': 5000, 'discount_cents': 300},  # $50 order gets $3 off
            {'threshold_cents': 10000, 'discount_cents': 700}, # $100 order gets $7 off
        ]

        for i, rule_info in enumerate(discount_rules_data):
            DiscountRule.objects.get_or_create(
                threshold_cents=rule_info['threshold_cents'],
                discount_cents=rule_info['discount_cents'],
                defaults={
                    'is_active': True,
                    'sort_order': i
                }
            )

        self.stdout.write(
            self.style.SUCCESS(
                f'Sample data created successfully!\n'
                f'- Organization: {org.name}\n'
                f'- Location: {location.name}\n'
                f'- Menu Categories: {MenuCategory.objects.filter(organization=org).count()}\n'
                f'- Menu Items: {MenuItem.objects.filter(organization=org).count()}\n'
                f'- Tables: {Table.objects.filter(location=location).count()}\n'
                f'- Coupons: {Coupon.objects.count()}\n'
                f'- Tip Tiers: {TipTier.objects.count()}\n'
                f'- Discount Rules: {DiscountRule.objects.count()}'
            )
        )
