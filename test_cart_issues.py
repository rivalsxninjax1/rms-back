#!/usr/bin/env python3
"""
Comprehensive test script to identify remaining cart issues.
This script will test both quantity decrement and order extras functionality.
"""

import os
import sys
import django
import json

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rms_backend.settings')
django.setup()

from django.test import Client
from django.contrib.sessions.models import Session

from menu.models import MenuItem, ModifierGroup, Modifier
from orders.models import OrderItem
from django.contrib.sessions.backends.db import SessionStore

def test_cart_functionality():
    print("=== Testing Cart Functionality ===")
    
    # Create a test client
    client = Client()
    
    # Test 1: Check if menu items exist
    print("\n1. Checking menu items...")
    menu_items = MenuItem.objects.all()[:5]
    for item in menu_items:
        print(f"   - {item.name} (ID: {item.id}) - NPR {item.price}")
    
    if not menu_items:
        print("   ERROR: No menu items found!")
        return False
    
    # Test 2: Add item to cart
    print("\n2. Testing add to cart...")
    test_item = menu_items[0]
    response = client.post('/api/orders/cart/items/', {
        'menu_item_id': test_item.id,
        'quantity': 2
    }, content_type='application/json')
    
    print(f"   Add to cart response: {response.status_code}")
    if response.status_code != 200:
        print(f"   ERROR: Failed to add item to cart: {response.content}")
        return False
    
    # Test 3: Check cart contents
    print("\n3. Checking cart contents...")
    response = client.get('/api/orders/cart-simple/')
    print(f"   Cart API response: {response.status_code}")
    
    if response.status_code == 200:
        cart_data = response.json()
        print(f"   Cart items: {len(cart_data.get('items', []))}")
        for item in cart_data.get('items', []):
            print(f"   - {item.get('name')} x{item.get('quantity')} = NPR {item.get('line_total')}")
    else:
        print(f"   ERROR: Failed to get cart contents: {response.content}")
        return False
    
    # Test 4: Test quantity decrement
    print("\n4. Testing quantity decrement...")
    if cart_data.get('items'):
        cart_item = cart_data['items'][0]
        item_id = cart_item['id']
        original_qty = cart_item['quantity']
        
        # Try to decrement quantity
        response = client.post('/api/orders/cart/items/', {
            'menu_item_id': item_id,
            'quantity': -1
        }, content_type='application/json')
        
        print(f"   Decrement response: {response.status_code}")
        
        # Check new quantity
        response = client.get('/api/orders/cart-simple/')
        if response.status_code == 200:
            new_cart_data = response.json()
            if new_cart_data.get('items'):
                new_qty = new_cart_data['items'][0]['quantity']
                print(f"   Original quantity: {original_qty}, New quantity: {new_qty}")
                
                if original_qty > 1 and new_qty == original_qty - 1:
                    print("   ✓ Quantity decrement working correctly")
                elif original_qty == 1 and new_qty == 1:
                    print("   ✓ Quantity stays at 1 (minimum) - FIXED")
                else:
                    print(f"   ✗ Unexpected quantity behavior: {original_qty} -> {new_qty}")
            else:
                if original_qty == 1:
                    print("   ✗ Item disappeared when quantity was 1 - ISSUE NOT FIXED")
                else:
                    print("   ✗ Item disappeared unexpectedly")
    
    # Test 5: Check modifiers
    print("\n5. Testing modifiers...")
    modifier_groups = ModifierGroup.objects.all()[:3]
    print(f"   Modifier groups found: {len(modifier_groups)}")
    
    for group in modifier_groups:
        modifiers = group.modifiers.all()[:2]
        print(f"   - {group.name}: {len(modifiers)} modifiers")
        for mod in modifiers:
            print(f"     • {mod.name} (+NPR {mod.price})")
    
    # Test 6: Check modifiers API
    print("\n6. Testing modifiers API...")
    response = client.get('/api/orders/cart/modifiers/')
    print(f"   Modifiers API response: {response.status_code}")
    
    if response.status_code == 200:
        modifiers_data = response.json()
        modifier_groups_api = modifiers_data.get('modifier_groups', [])
        print(f"   API returned {len(modifier_groups_api)} modifier groups")
        
        if len(modifier_groups_api) > 0:
            print("   ✓ Modifiers API working correctly")
            for group in modifier_groups_api[:2]:
                print(f"   - {group.get('name')}: {len(group.get('modifiers', []))} modifiers")
        else:
            print("   ✗ Modifiers API returning empty data - ISSUE NOT FIXED")
    else:
        print(f"   ✗ Modifiers API failed: {response.content}")
    
    print("\n=== Test Summary ===")
    print("Please check the cart page manually to verify:")
    print("1. Items don't disappear when clicking minus button at quantity 1")
    print("2. Order extras section appears and functions properly")
    print("3. Console logs show proper initialization")
    
    return True

if __name__ == '__main__':
    test_cart_functionality()