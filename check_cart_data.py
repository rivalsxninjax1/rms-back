#!/usr/bin/env python3
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rms_backend.settings')
django.setup()

from orders.models import Cart, CartItem
from orders.serializers import CartSerializer

print('=== Cart Data Analysis ===')
print(f'Total carts: {Cart.objects.count()}')
print(f'Total cart items: {CartItem.objects.count()}')

print('\n=== Cart Details ===')
for cart in Cart.objects.all():
    print(f'Cart {cart.cart_uuid}: {cart.items.count()} items, Status: {cart.status}')
    print(f'  User: {cart.user}, Session: {cart.session_key}')
    for item in cart.items.all():
        print(f'  - {item.menu_item.name}: qty {item.quantity}, price: {item.line_total}')
    
    # Test serialization
    serializer = CartSerializer(cart)
    print(f'  Serialized items count: {len(serializer.data.get("items", []))}')
    print(f'  Serialized data keys: {list(serializer.data.keys())}')
    print('---')