#!/usr/bin/env python3
"""
Test script to verify cart add/subtract button functionality
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rms_backend.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from menu.models import MenuItem
from orders.models import Order, OrderItem

def test_cart_buttons():
    print("=== Testing Cart Add/Subtract Button Functionality ===")
    
    client = Client()
    
    # Clear any existing cart
    print("\n1. Clearing cart...")
    client.post('/api/cart/sync/', 
                content_type='application/json',
                data='{"items": []}')
    
    # Add an item to cart
    print("\n2. Adding pizza (ID: 1) with quantity 3...")
    add_response = client.post('/api/orders/cart/items/', {
        'menu_item_id': 1,
        'quantity': 3
    })
    print(f"   Add response: {add_response.status_code}")
    
    # Check cart contents
    cart_response = client.get('/api/orders/cart-simple/')
    if cart_response.status_code == 200:
        cart_data = cart_response.json()
        items = cart_data.get('items', [])
        pizza_item = next((item for item in items if item.get('id') == 1), None)
        if pizza_item:
            qty = pizza_item.get('quantity')
            print(f"   ✓ Pizza quantity: {qty} (should be 3)")
        else:
            print("   ✗ Pizza item not found in cart!")
    
    # Test increment button (+1)
    print("\n3. Testing increment button (+1)...")
    inc_response = client.post('/api/orders/cart/items/', {
        'menu_item_id': 1,
        'quantity': 1  # Add 1 more
    })
    print(f"   Increment response: {inc_response.status_code}")
    
    cart_response = client.get('/api/orders/cart-simple/')
    if cart_response.status_code == 200:
        cart_data = cart_response.json()
        items = cart_data.get('items', [])
        pizza_item = next((item for item in items if item.get('id') == 1), None)
        if pizza_item:
            qty = pizza_item.get('quantity')
            print(f"   ✓ Pizza quantity after increment: {qty} (should be 4)")
            if qty == 4:
                print("   ✓ INCREMENT WORKING CORRECTLY")
            else:
                print("   ✗ INCREMENT NOT WORKING - Expected 4, got", qty)
    
    # Test decrement button (-1)
    print("\n4. Testing decrement button (-1)...")
    dec_response = client.post('/api/orders/cart/items/', {
        'menu_item_id': 1,
        'quantity': -1  # Subtract 1
    })
    print(f"   Decrement response: {dec_response.status_code}")
    
    cart_response = client.get('/api/orders/cart-simple/')
    if cart_response.status_code == 200:
        cart_data = cart_response.json()
        items = cart_data.get('items', [])
        pizza_item = next((item for item in items if item.get('id') == 1), None)
        if pizza_item:
            qty = pizza_item.get('quantity')
            print(f"   ✓ Pizza quantity after decrement: {qty} (should be 3)")
            if qty == 3:
                print("   ✓ DECREMENT WORKING CORRECTLY")
            else:
                print("   ✗ DECREMENT NOT WORKING - Expected 3, got", qty)
    
    # Test multiple decrements to quantity 1
    print("\n5. Testing multiple decrements to quantity 1...")
    for i in range(2):  # Decrement 2 more times to get to 1
        client.post('/api/orders/cart/items/', {
            'menu_item_id': 1,
            'quantity': -1
        })
    
    cart_response = client.get('/api/orders/cart-simple/')
    if cart_response.status_code == 200:
        cart_data = cart_response.json()
        items = cart_data.get('items', [])
        pizza_item = next((item for item in items if item.get('id') == 1), None)
        if pizza_item:
            qty = pizza_item.get('quantity')
            print(f"   ✓ Pizza quantity at minimum: {qty} (should be 1)")
            if qty == 1:
                print("   ✓ MINIMUM QUANTITY MAINTAINED")
            else:
                print("   ✗ MINIMUM QUANTITY ISSUE - Expected 1, got", qty)
    
    # Test trying to decrement below 1 (frontend should prevent this)
    print("\n6. Testing decrement below 1 (should be prevented by frontend)...")
    dec_response = client.post('/api/orders/cart/items/', {
        'menu_item_id': 1,
        'quantity': -1  # Try to go below 1
    })
    print(f"   Decrement response: {dec_response.status_code}")
    
    cart_response = client.get('/api/orders/cart-simple/')
    if cart_response.status_code == 200:
        cart_data = cart_response.json()
        items = cart_data.get('items', [])
        pizza_item = next((item for item in items if item.get('id') == 1), None)
        if pizza_item:
            qty = pizza_item.get('quantity')
            print(f"   Pizza quantity after attempted below-1 decrement: {qty}")
            if qty == 0:
                print("   ✓ ITEM REMOVED (backend behavior)")
            elif qty == 1:
                print("   ✓ MINIMUM QUANTITY MAINTAINED (frontend prevention)")
        else:
            print("   ✓ ITEM REMOVED FROM CART (backend behavior)")
    
    print("\n=== Cart Button Test Complete ===")

if __name__ == '__main__':
    test_cart_buttons()