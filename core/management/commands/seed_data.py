from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from decimal import Decimal
from menu.models import MenuCategory, MenuItem, ModifierGroup, Modifier
from core.models import ServiceType, Table, Organization, Location
from reservations.models import Table as ReservationTable
import random

User = get_user_model()

class Command(BaseCommand):
    help = 'Seed the database with sample data for testing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing data before seeding',
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write('Clearing existing data...')
            MenuItem.objects.all().delete()
            MenuCategory.objects.all().delete()
            ModifierGroup.objects.all().delete()
            Modifier.objects.all().delete()
            ServiceType.objects.all().delete()
            Table.objects.all().delete()
            Location.objects.all().delete()
            Organization.objects.all().delete()
            if hasattr(ReservationTable, 'objects'):
                ReservationTable.objects.all().delete()

        self.stdout.write('Creating sample data...')

        # Create organization
        organization, created = Organization.objects.get_or_create(
            name='Sample Restaurant',
            defaults={
                'tax_percent': Decimal('8.25'),
                'address': '123 Main Street, City, State 12345',
                'phone': '+1234567890',
                'email': 'info@samplerestaurant.com',
            }
        )
        if created:
            self.stdout.write(f'Created organization: {organization.name}')

        # Create location
        location, created = Location.objects.get_or_create(
            organization=organization,
            name='Main Location',
            defaults={
                'address': '123 Main Street, City, State 12345',
                'is_active': True,
            }
        )
        if created:
            self.stdout.write(f'Created location: {location.name}')

        # Create admin user if not exists
        if not User.objects.filter(is_superuser=True).exists():
            admin_user = User.objects.create_superuser(
                username='admin',
                email='admin@restaurant.com',
                password='admin123'
            )
            self.stdout.write(f'Created admin user: {admin_user.username}')

        # Create menu categories
        categories_data = [
            {'name': 'Appetizers', 'description': 'Start your meal with our delicious appetizers'},
            {'name': 'Main Courses', 'description': 'Hearty and satisfying main dishes'},
            {'name': 'Desserts', 'description': 'Sweet treats to end your meal'},
            {'name': 'Beverages', 'description': 'Refreshing drinks and beverages'},
        ]

        categories = []
        for cat_data in categories_data:
            category, created = MenuCategory.objects.get_or_create(
                organization=organization,
                name=cat_data['name'],
                defaults={'description': cat_data['description']}
            )
            categories.append(category)
            if created:
                self.stdout.write(f'Created category: {category.name}')

        # Note: Modifier groups and modifiers are created per menu item
        # and would require more complex logic. Skipping for basic seed data.

        # Create menu items
        menu_items_data = [
            # Appetizers
            {'name': 'Caesar Salad', 'description': 'Fresh romaine lettuce with parmesan cheese and croutons', 'price': Decimal('8.99'), 'category': 'Appetizers', 'is_vegetarian': True, 'prep_time': 10},
            {'name': 'Buffalo Wings', 'description': 'Spicy chicken wings served with blue cheese dip', 'price': Decimal('12.99'), 'category': 'Appetizers', 'prep_time': 15},
            {'name': 'Mozzarella Sticks', 'description': 'Crispy breaded mozzarella with marinara sauce', 'price': Decimal('9.99'), 'category': 'Appetizers', 'is_vegetarian': True, 'prep_time': 12},
            
            # Main Courses
            {'name': 'Grilled Salmon', 'description': 'Fresh Atlantic salmon with lemon herb butter', 'price': Decimal('24.99'), 'category': 'Main Courses', 'prep_time': 20},
            {'name': 'Ribeye Steak', 'description': '12oz prime ribeye steak cooked to perfection', 'price': Decimal('32.99'), 'category': 'Main Courses', 'prep_time': 25},
            {'name': 'Chicken Parmesan', 'description': 'Breaded chicken breast with marinara and mozzarella', 'price': Decimal('19.99'), 'category': 'Main Courses', 'prep_time': 22},
            {'name': 'Vegetarian Burger', 'description': 'Plant-based patty with fresh vegetables', 'price': Decimal('16.99'), 'category': 'Main Courses', 'is_vegetarian': True, 'prep_time': 15},
            
            # Pasta
            {'name': 'Spaghetti Carbonara', 'description': 'Classic Italian pasta with eggs, cheese, and pancetta', 'price': Decimal('17.99'), 'category': 'Pasta', 'prep_time': 18},
            {'name': 'Penne Arrabbiata', 'description': 'Spicy tomato sauce with garlic and red peppers', 'price': Decimal('15.99'), 'category': 'Pasta', 'is_vegetarian': True, 'prep_time': 16},
            {'name': 'Fettuccine Alfredo', 'description': 'Rich and creamy white sauce with parmesan', 'price': Decimal('16.99'), 'category': 'Pasta', 'is_vegetarian': True, 'prep_time': 14},
            
            # Salads
            {'name': 'Greek Salad', 'description': 'Mixed greens with feta, olives, and tomatoes', 'price': Decimal('11.99'), 'category': 'Salads', 'is_vegetarian': True, 'prep_time': 8},
            {'name': 'Cobb Salad', 'description': 'Mixed greens with bacon, blue cheese, and egg', 'price': Decimal('13.99'), 'category': 'Salads', 'prep_time': 10},
            
            # Desserts
            {'name': 'Chocolate Cake', 'description': 'Rich chocolate layer cake with fudge frosting', 'price': Decimal('7.99'), 'category': 'Desserts', 'is_vegetarian': True, 'prep_time': 5},
            {'name': 'Tiramisu', 'description': 'Classic Italian dessert with coffee and mascarpone', 'price': Decimal('8.99'), 'category': 'Desserts', 'is_vegetarian': True, 'prep_time': 5},
            {'name': 'Cheesecake', 'description': 'New York style cheesecake with berry compote', 'price': Decimal('6.99'), 'category': 'Desserts', 'is_vegetarian': True, 'prep_time': 5},
            
            # Beverages
            {'name': 'Coffee', 'description': 'Freshly brewed coffee', 'price': Decimal('2.99'), 'category': 'Beverages', 'is_vegetarian': True, 'prep_time': 3},
            {'name': 'Fresh Orange Juice', 'description': 'Freshly squeezed orange juice', 'price': Decimal('4.99'), 'category': 'Beverages', 'is_vegetarian': True, 'prep_time': 2},
            {'name': 'Craft Beer', 'description': 'Local craft beer selection', 'price': Decimal('5.99'), 'category': 'Beverages', 'prep_time': 2},
            {'name': 'House Wine', 'description': 'Red or white wine by the glass', 'price': Decimal('7.99'), 'category': 'Beverages', 'prep_time': 2},
        ]

        for item_data in menu_items_data:
            category = next((cat for cat in categories if cat.name == item_data['category']), None)
            if category:
                menu_item, created = MenuItem.objects.get_or_create(
                    organization=organization,
                    name=item_data['name'],
                    category=category,
                    defaults={
                        'description': item_data['description'],
                        'price': item_data['price'],
                        'is_vegetarian': item_data.get('is_vegetarian', False),
                        'preparation_time': item_data.get('prep_time', 10),
                        'is_available': True
                    }
                )
                if created:
                    self.stdout.write(f'Created menu item: {menu_item.name}')

        # Create service types
        service_types_data = [
            {'name': 'Dine In', 'code': 'DINE_IN', 'description': 'Eat at the restaurant', 'requires_table': True, 'allows_reservations': True},
            {'name': 'Takeout', 'code': 'TAKEOUT', 'description': 'Order for pickup', 'requires_table': False, 'allows_reservations': False},
            {'name': 'Delivery', 'code': 'DELIVERY', 'description': 'Delivered to your location', 'requires_table': False, 'allows_reservations': False},
        ]

        for st_data in service_types_data:
            service_type, created = ServiceType.objects.get_or_create(
                code=st_data['code'],
                defaults={
                    'name': st_data['name'],
                    'description': st_data['description'],
                    'requires_table': st_data['requires_table'],
                    'allows_reservations': st_data['allows_reservations'],
                }
            )
            if created:
                self.stdout.write(f'Created service type: {service_type.name}')

        # Create tables
        for i in range(1, 21):  # Create 20 tables
            capacity = random.choice([2, 4, 6, 8])
            table, created = Table.objects.get_or_create(
                location=location,
                table_number=str(i),
                defaults={
                    'capacity': capacity,
                    'is_active': True,
                }
            )
            if created:
                self.stdout.write(f'Created table {table.table_number} (capacity: {capacity})')

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully seeded database with:\n'
                f'- {MenuCategory.objects.count()} categories\n'
                f'- {MenuItem.objects.count()} menu items\n'
                f'- {ModifierGroup.objects.count()} modifier groups\n'
                f'- {Modifier.objects.count()} modifiers\n'
                f'- {ServiceType.objects.count()} service types\n'
                f'- {Table.objects.count()} tables'
            )
        )