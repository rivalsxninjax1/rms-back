#!/usr/bin/env python3
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rms_backend.settings')
django.setup()

from django.test import Client
from menu.models import ModifierGroup, Modifier, MenuItem
from orders.views import _cart_get, _normalize_items

def debug_modifiers():
    print('=== Debugging Modifiers API Issue ===')
    
    # Create a test client
    client = Client()
    
    # Check current cart contents
    print('\n1. Checking current cart contents...')
    response = client.get('/api/orders/cart-simple/')
    print(f'   Cart API response: {response.status_code}')
    
    if response.status_code == 200:
        cart_data = response.json()
        items = cart_data.get('items', [])
        print(f'   Cart has {len(items)} items:')
        for item in items:
            print(f'   - Item ID: {item.get("id")}, Name: {item.get("name")}, Qty: {item.get("quantity")}')
    
    # Add an item to cart first
    print('\n2. Adding item to cart...')
    add_response = client.post('/api/orders/cart/items/', {
        'menu_item_id': 1,
        'quantity': 1
    })
    print(f'   Add item response: {add_response.status_code}')
    
    # Check cart again
    print('\n3. Checking cart after adding item...')
    response = client.get('/api/orders/cart-simple/')
    if response.status_code == 200:
        cart_data = response.json()
        items = cart_data.get('items', [])
        print(f'   Cart now has {len(items)} items:')
        menu_item_ids = []
        for item in items:
            item_id = item.get('id')
            menu_item_ids.append(item_id)
            print(f'   - Item ID: {item_id}, Name: {item.get("name")}, Qty: {item.get("quantity")}')
        
        # Check if modifier groups exist for these items
        print('\n4. Checking modifier groups for cart items...')
        for item_id in menu_item_ids:
            modifier_groups = ModifierGroup.objects.filter(menu_item_id=item_id)
            print(f'   Item {item_id} has {len(modifier_groups)} modifier groups:')
            for group in modifier_groups:
                modifiers = group.modifiers.filter(is_available=True)
                print(f'   - Group: {group.name} ({len(modifiers)} available modifiers)')
                for mod in modifiers[:3]:  # Show first 3
                    print(f'     • {mod.name}: NPR {mod.price}')
    
    # Test modifiers API
    print('\n5. Testing modifiers API...')
    mod_response = client.get('/api/orders/cart/modifiers/')
    print(f'   Modifiers API response: {mod_response.status_code}')
    
    if mod_response.status_code == 200:
        mod_data = mod_response.json()
        modifier_groups_api = mod_data.get('modifier_groups', [])
        print(f'   API returned {len(modifier_groups_api)} modifier groups')
        
        for group in modifier_groups_api:
            print(f'   - {group.get("name")}: {len(group.get("modifiers", []))} modifiers')
            for mod in group.get('modifiers', [])[:2]:  # Show first 2
                print(f'     • {mod.get("name")}: NPR {mod.get("price")}')
    else:
        print(f'   API failed: {mod_response.content}')
    
    # Check if we need to create modifier groups for testing
    print('\n6. Checking if we need to create test modifier groups...')
    menu_items = MenuItem.objects.all()[:3]
    for item in menu_items:
        groups = ModifierGroup.objects.filter(menu_item=item)
        print(f'   MenuItem {item.id} ({item.name}) has {len(groups)} modifier groups')
        
        if len(groups) == 0:
            print(f'   Creating test modifier group for {item.name}...')
            # Create a test modifier group
            group = ModifierGroup.objects.create(
                name=f'Extras for {item.name}',
                menu_item=item,
                is_required=False,
                min_select=0,
                max_select=5,
                sort_order=1
            )
            
            # Create some test modifiers
            Modifier.objects.create(
                name='Extra Cheese',
                price=50.00,
                modifier_group=group,
                is_available=True,
                sort_order=1
            )
            Modifier.objects.create(
                name='Extra Sauce',
                price=25.00,
                modifier_group=group,
                is_available=True,
                sort_order=2
            )
            print(f'   Created modifier group with 2 modifiers for {item.name}')
    
    print('\n=== Debug Complete ===')
    return True

if __name__ == '__main__':
    debug_modifiers()