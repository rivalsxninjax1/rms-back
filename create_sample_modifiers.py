#!/usr/bin/env python3
import os
import sys
import django
from decimal import Decimal

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rms_backend.settings')
django.setup()

from menu.models import ModifierGroup, Modifier, MenuItem

print('=== Creating Sample Modifiers ===')

# Get some menu items to add modifiers to
pizza = MenuItem.objects.filter(name__icontains='pizza').first()
chicken = MenuItem.objects.filter(name__icontains='chicken').first()
wings = MenuItem.objects.filter(name__icontains='wings').first()

if pizza:
    print(f'Adding modifiers to: {pizza.name}')
    
    # Pizza Size Group
    size_group = ModifierGroup.objects.create(
        menu_item=pizza,
        name='Pizza Size',
        is_required=True,
        min_select=1,
        max_select=1,
        sort_order=1
    )
    
    Modifier.objects.create(
        modifier_group=size_group,
        name='Small (8")',
        price=Decimal('0.00'),
        sort_order=1
    )
    
    Modifier.objects.create(
        modifier_group=size_group,
        name='Medium (12")',
        price=Decimal('50.00'),
        sort_order=2
    )
    
    Modifier.objects.create(
        modifier_group=size_group,
        name='Large (16")',
        price=Decimal('100.00'),
        sort_order=3
    )
    
    # Pizza Toppings Group
    toppings_group = ModifierGroup.objects.create(
        menu_item=pizza,
        name='Extra Toppings',
        is_required=False,
        min_select=0,
        max_select=5,
        sort_order=2
    )
    
    Modifier.objects.create(
        modifier_group=toppings_group,
        name='Extra Cheese',
        price=Decimal('25.00'),
        sort_order=1
    )
    
    Modifier.objects.create(
        modifier_group=toppings_group,
        name='Pepperoni',
        price=Decimal('30.00'),
        sort_order=2
    )
    
    Modifier.objects.create(
        modifier_group=toppings_group,
        name='Mushrooms',
        price=Decimal('20.00'),
        sort_order=3
    )
    
    Modifier.objects.create(
        modifier_group=toppings_group,
        name='Bell Peppers',
        price=Decimal('15.00'),
        sort_order=4
    )

if chicken:
    print(f'Adding modifiers to: {chicken.name}')
    
    # Spice Level Group
    spice_group = ModifierGroup.objects.create(
        menu_item=chicken,
        name='Spice Level',
        is_required=True,
        min_select=1,
        max_select=1,
        sort_order=1
    )
    
    Modifier.objects.create(
        modifier_group=spice_group,
        name='Mild',
        price=Decimal('0.00'),
        sort_order=1
    )
    
    Modifier.objects.create(
        modifier_group=spice_group,
        name='Medium',
        price=Decimal('0.00'),
        sort_order=2
    )
    
    Modifier.objects.create(
        modifier_group=spice_group,
        name='Hot',
        price=Decimal('0.00'),
        sort_order=3
    )
    
    Modifier.objects.create(
        modifier_group=spice_group,
        name='Extra Hot',
        price=Decimal('10.00'),
        sort_order=4
    )

if wings:
    print(f'Adding modifiers to: {wings.name}')
    
    # Wings Sauce Group
    sauce_group = ModifierGroup.objects.create(
        menu_item=wings,
        name='Wing Sauce',
        is_required=False,
        min_select=0,
        max_select=2,
        sort_order=1
    )
    
    Modifier.objects.create(
        modifier_group=sauce_group,
        name='Buffalo Sauce',
        price=Decimal('0.00'),
        sort_order=1
    )
    
    Modifier.objects.create(
        modifier_group=sauce_group,
        name='BBQ Sauce',
        price=Decimal('5.00'),
        sort_order=2
    )
    
    Modifier.objects.create(
        modifier_group=sauce_group,
        name='Honey Mustard',
        price=Decimal('5.00'),
        sort_order=3
    )

print('\n=== Final Count ===')
print(f'ModifierGroups: {ModifierGroup.objects.count()}')
print(f'Modifiers: {Modifier.objects.count()}')

print('\n=== Created Modifier Groups ===')
for mg in ModifierGroup.objects.all():
    print(f'  {mg.name} for {mg.menu_item.name} (Required: {mg.is_required})')
    for mod in mg.modifiers.all():
        print(f'    - {mod.name}: NPR {mod.price}')