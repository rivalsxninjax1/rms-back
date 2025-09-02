from django.core.management.base import BaseCommand
from decimal import Decimal
from menu.models import MenuItem, ModifierGroup, Modifier


class Command(BaseCommand):
    help = 'Seed the database with sample modifier groups and modifiers'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing modifier data before seeding',
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write('Clearing existing modifier data...')
            Modifier.objects.all().delete()
            ModifierGroup.objects.all().delete()

        self.stdout.write('Creating sample modifier groups and modifiers...')

        # Get some menu items to attach modifiers to
        menu_items = MenuItem.objects.all()[:10]  # Get first 10 items
        
        if not menu_items:
            self.stdout.write(self.style.ERROR('No menu items found. Please run seed_data first.'))
            return

        # Create modifier groups and modifiers for different types of items
        modifier_data = [
            {
                'group_name': 'Size Options',
                'description': 'Choose your preferred size',
                'is_required': True,
                'min_selections': 1,
                'max_selections': 1,
                'selection_type': 'single',
                'modifiers': [
                    {'name': 'Small', 'price': Decimal('0.00'), 'description': 'Regular size'},
                    {'name': 'Medium', 'price': Decimal('2.00'), 'description': 'Medium size (+$2.00)'},
                    {'name': 'Large', 'price': Decimal('4.00'), 'description': 'Large size (+$4.00)'},
                    {'name': 'Extra Large', 'price': Decimal('6.00'), 'description': 'Extra large size (+$6.00)'},
                ]
            },
            {
                'group_name': 'Extra Toppings',
                'description': 'Add extra toppings to your dish',
                'is_required': False,
                'min_selections': 0,
                'max_selections': 5,
                'selection_type': 'multiple',
                'modifiers': [
                    {'name': 'Extra Cheese', 'price': Decimal('1.50'), 'description': 'Additional cheese'},
                    {'name': 'Bacon', 'price': Decimal('2.00'), 'description': 'Crispy bacon strips'},
                    {'name': 'Mushrooms', 'price': Decimal('1.00'), 'description': 'Fresh mushrooms'},
                    {'name': 'Onions', 'price': Decimal('0.50'), 'description': 'Diced onions'},
                    {'name': 'Peppers', 'price': Decimal('0.75'), 'description': 'Bell peppers'},
                    {'name': 'Olives', 'price': Decimal('1.00'), 'description': 'Black or green olives'},
                    {'name': 'Tomatoes', 'price': Decimal('0.50'), 'description': 'Fresh tomatoes'},
                ]
            },
            {
                'group_name': 'Cooking Style',
                'description': 'How would you like it prepared?',
                'is_required': False,
                'min_selections': 0,
                'max_selections': 1,
                'selection_type': 'single',
                'modifiers': [
                    {'name': 'Rare', 'price': Decimal('0.00'), 'description': 'Rare cooking'},
                    {'name': 'Medium Rare', 'price': Decimal('0.00'), 'description': 'Medium rare cooking'},
                    {'name': 'Medium', 'price': Decimal('0.00'), 'description': 'Medium cooking'},
                    {'name': 'Medium Well', 'price': Decimal('0.00'), 'description': 'Medium well cooking'},
                    {'name': 'Well Done', 'price': Decimal('0.00'), 'description': 'Well done cooking'},
                ]
            },
            {
                'group_name': 'Sauce Options',
                'description': 'Choose your sauce',
                'is_required': False,
                'min_selections': 0,
                'max_selections': 2,
                'selection_type': 'multiple',
                'modifiers': [
                    {'name': 'Marinara', 'price': Decimal('0.00'), 'description': 'Classic marinara sauce'},
                    {'name': 'Alfredo', 'price': Decimal('1.00'), 'description': 'Creamy alfredo sauce'},
                    {'name': 'Pesto', 'price': Decimal('1.50'), 'description': 'Basil pesto sauce'},
                    {'name': 'BBQ Sauce', 'price': Decimal('0.50'), 'description': 'Tangy BBQ sauce'},
                    {'name': 'Hot Sauce', 'price': Decimal('0.00'), 'description': 'Spicy hot sauce'},
                    {'name': 'Ranch', 'price': Decimal('0.50'), 'description': 'Creamy ranch dressing'},
                ]
            },
            {
                'group_name': 'Side Dishes',
                'description': 'Add a side to your meal',
                'is_required': False,
                'min_selections': 0,
                'max_selections': 3,
                'selection_type': 'multiple',
                'modifiers': [
                    {'name': 'French Fries', 'price': Decimal('3.00'), 'description': 'Crispy french fries'},
                    {'name': 'Onion Rings', 'price': Decimal('3.50'), 'description': 'Beer battered onion rings'},
                    {'name': 'Side Salad', 'price': Decimal('4.00'), 'description': 'Fresh garden salad'},
                    {'name': 'Garlic Bread', 'price': Decimal('2.50'), 'description': 'Toasted garlic bread'},
                    {'name': 'Coleslaw', 'price': Decimal('2.00'), 'description': 'Creamy coleslaw'},
                    {'name': 'Mashed Potatoes', 'price': Decimal('3.00'), 'description': 'Creamy mashed potatoes'},
                ]
            }
        ]

        created_groups = 0
        created_modifiers = 0

        # Create modifier groups for each menu item
        for menu_item in menu_items:
            # Assign different modifier groups based on item type
            item_name_lower = menu_item.name.lower()
            
            # Determine which modifier groups to add based on item type
            groups_to_add = []
            
            if any(word in item_name_lower for word in ['burger', 'sandwich', 'pizza']):
                groups_to_add = [0, 1, 3, 4]  # Size, Toppings, Sauce, Sides
            elif any(word in item_name_lower for word in ['steak', 'salmon', 'chicken']):
                groups_to_add = [2, 3, 4]  # Cooking Style, Sauce, Sides
            elif any(word in item_name_lower for word in ['pasta', 'spaghetti', 'penne', 'fettuccine']):
                groups_to_add = [0, 3, 4]  # Size, Sauce, Sides
            elif any(word in item_name_lower for word in ['salad']):
                groups_to_add = [0, 1, 4]  # Size, Toppings, Sides
            elif any(word in item_name_lower for word in ['wings']):
                groups_to_add = [1, 3, 4]  # Toppings, Sauce, Sides
            else:
                # Default: add size and sides for other items
                groups_to_add = [0, 4]  # Size, Sides

            for group_index in groups_to_add:
                group_data = modifier_data[group_index]
                
                # Determine appropriate display style based on selection type
                display_style = 'radio' if group_data['selection_type'] == 'single' else 'checkbox'
                
                # Create modifier group
                modifier_group, group_created = ModifierGroup.objects.get_or_create(
                    menu_item=menu_item,
                    name=group_data['group_name'],
                    defaults={
                        'description': group_data['description'],
                        'is_required': group_data['is_required'],
                        'min_selections': group_data['min_selections'],
                        'max_selections': group_data['max_selections'],
                        'selection_type': group_data['selection_type'],
                        'display_style': display_style,
                        'is_active': True,
                        'sort_order': group_index + 1,
                    }
                )
                
                if group_created:
                    created_groups += 1
                    self.stdout.write(f'Created modifier group: {modifier_group.name} for {menu_item.name}')
                    
                    # Create modifiers for this group
                    for mod_index, mod_data in enumerate(group_data['modifiers']):
                        modifier, mod_created = Modifier.objects.get_or_create(
                            modifier_group=modifier_group,
                            name=mod_data['name'],
                            defaults={
                                'description': mod_data['description'],
                                'price': mod_data['price'],
                                'is_available': True,
                                'sort_order': mod_index + 1,
                                'modifier_type': 'addon',
                            }
                        )
                        
                        if mod_created:
                            created_modifiers += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully seeded modifier data:\n'
                f'- {created_groups} modifier groups created\n'
                f'- {created_modifiers} modifiers created\n'
                f'- Total modifier groups: {ModifierGroup.objects.count()}\n'
                f'- Total modifiers: {Modifier.objects.count()}'
            )
        )