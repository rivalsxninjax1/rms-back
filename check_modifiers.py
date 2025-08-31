#!/usr/bin/env python3
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rms_backend.settings')
django.setup()

from menu.models import ModifierGroup, Modifier, MenuItem

print('=== Database Content Check ===')
print(f'MenuItems: {MenuItem.objects.count()}')
print(f'ModifierGroups: {ModifierGroup.objects.count()}')
print(f'Modifiers: {Modifier.objects.count()}')

print('\n=== Sample MenuItems ===')
for item in MenuItem.objects.all()[:5]:
    print(f'  {item.id}: {item.name} - NPR {item.price}')

print('\n=== Sample ModifierGroups ===')
for mg in ModifierGroup.objects.all()[:5]:
    print(f'  {mg.id}: {mg.name} for {mg.menu_item.name}')
    for mod in mg.modifiers.all()[:3]:
        print(f'    - {mod.name}: NPR {mod.price}')

print('\n=== Cart Items Check ===')
# Check what items are currently in a sample session
from django.contrib.sessions.models import Session
from django.contrib.sessions.backends.db import SessionStore

sessions = Session.objects.all()[:3]
for session in sessions:
    store = SessionStore(session_key=session.session_key)
    cart_items = store.get('cart_items', [])
    if cart_items:
        print(f'Session {session.session_key[:8]}... has cart items:')
        for item in cart_items:
            print(f'  - Item ID: {item.get("id")}, Qty: {item.get("quantity")}')