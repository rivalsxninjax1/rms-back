#!/usr/bin/env python3

import os
import sys
import django
from datetime import timedelta
from django.utils import timezone

# Add the project directory to Python path
sys.path.append('/Users/sickboi/Desktop/rms-back')

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rms.settings.development')
django.setup()

from orders.models import Cart, CartItem

def main():
    print("=== Cart Status Analysis ===")
    
    # Get all carts
    all_carts = Cart.objects.all().order_by('-updated_at')
    print(f"Total carts: {all_carts.count()}")
    
    # Check active carts
    active_carts = Cart.objects.filter(status=Cart.STATUS_ACTIVE)
    print(f"Active carts: {active_carts.count()}")
    
    # Check expired carts
    expired_carts = Cart.objects.filter(status=Cart.STATUS_EXPIRED)
    print(f"Expired carts: {expired_carts.count()}")
    
    print("\n=== Recent Cart Details ===")
    for cart in all_carts[:5]:  # Show last 5 carts
        items_count = cart.items.count()
        time_since_update = timezone.now() - cart.updated_at
        minutes_since_update = time_since_update.total_seconds() / 60
        
        print(f"Cart {cart.cart_uuid}:")
        print(f"  Status: {cart.status}")
        print(f"  Items: {items_count}")
        print(f"  Updated: {cart.updated_at}")
        print(f"  Minutes since update: {minutes_since_update:.1f}")
        print(f"  Session key: {cart.session_key}")
        print(f"  User: {cart.user}")
        print()
    
    # Check if any carts should be active but are expired
    recent_threshold = timezone.now() - timedelta(minutes=25)
    recently_updated_expired = Cart.objects.filter(
        status=Cart.STATUS_EXPIRED,
        updated_at__gt=recent_threshold
    )
    
    if recently_updated_expired.exists():
        print(f"\n⚠️  Found {recently_updated_expired.count()} carts that were expired but updated recently!")
        for cart in recently_updated_expired:
            print(f"  Cart {cart.cart_uuid}: updated {cart.updated_at}, status: {cart.status}")
    
    # Check cart items in expired carts
    expired_with_items = Cart.objects.filter(
        status=Cart.STATUS_EXPIRED,
        items__isnull=False
    ).distinct()
    
    if expired_with_items.exists():
        print(f"\n⚠️  Found {expired_with_items.count()} expired carts that still have items!")
        for cart in expired_with_items:
            items_count = cart.items.count()
            print(f"  Cart {cart.cart_uuid}: {items_count} items, status: {cart.status}")

if __name__ == '__main__':
    main()