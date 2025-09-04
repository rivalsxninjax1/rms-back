from decimal import Decimal

import pytest
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

from tests.factories import UserFactory
from tests.factories.menu import MenuItemFactory, ModifierGroupFactory, ModifierFactory
from orders.models import Cart


@pytest.mark.django_db
def test_guest_cart_sticky_cookie_and_persist(auth_api_client: APIClient):
    # Unauthenticated client
    client = APIClient()

    # Hitting carts list should create or fetch a cart and set sticky cookie
    r1 = client.get('/api/carts/')
    assert r1.status_code == 200
    cart_uuid = r1.data.get('cart_uuid')
    assert cart_uuid
    # Cookie present (session or custom cart cookie)
    cookies = client.cookies
    assert cookies  # Has sessionid or custom cart cookie

    # Create a menu item and add to cart
    item = MenuItemFactory()
    r2 = client.post('/api/carts/add_item/', data={
        'menu_item_id': item.id,
        'quantity': 2,
    }, format='json')
    assert r2.status_code in (200, 201)

    # Fetch again; should be same cart_uuid
    r3 = client.get('/api/carts/')
    assert r3.status_code == 200
    assert r3.data.get('cart_uuid') == cart_uuid


@pytest.mark.django_db
def test_guest_to_user_cart_merge_preserves_modifiers():
    client = APIClient()
    # Build menu: item with modifier group + modifier
    item = MenuItemFactory()
    group = ModifierGroupFactory(menu_item=item)
    mod1 = ModifierFactory(modifier_group=group)

    # Guest cart add item with modifiers
    r1 = client.get('/api/carts/')
    assert r1.status_code == 200
    anon_uuid = r1.data['cart_uuid']
    r2 = client.post('/api/carts/add_item/', data={
        'menu_item_id': item.id,
        'quantity': 1,
        'selected_modifiers': [
            {'modifier_id': mod1.id, 'quantity': 2},
        ],
        'notes': 'extra spicy',
    }, format='json')
    assert r2.status_code in (200, 201)

    # Now authenticate user and merge
    user = UserFactory()
    client.force_authenticate(user=user)
    r3 = client.post('/api/carts/merge/', data={
        'anonymous_cart_uuid': anon_uuid
    }, format='json')
    assert r3.status_code == 200

    # Verify user's active cart has the item and modifiers preserved
    r4 = client.get('/api/carts/')
    assert r4.status_code == 200
    data = r4.data
    assert data['cart_uuid']
    # We rely on items being returned via CartSerializer read-only
    # (it returns items as read-only list)
    # If not included directly, optionally fetch via a separate endpoint
    # but here we expect items are included
    # So we just verify DB state
    cart = Cart.objects.filter(user=user, status=Cart.STATUS_ACTIVE).order_by('-updated_at').first()
    assert cart is not None
    it = cart.items.first()
    assert it is not None
    # selected_modifiers must have same modifier_id and quantity
    mods = it.selected_modifiers or []
    assert any(m.get('modifier_id') == mod1.id and int(m.get('quantity', 0)) == 2 for m in mods)
    assert it.notes == 'extra spicy'


@pytest.mark.django_db
def test_merge_uses_active_cart_not_converted():
    client = APIClient()
    # Guest creates a cart
    r1 = client.get('/api/carts/')
    anon_uuid = r1.data['cart_uuid']

    # Create user and a non-active (converted) cart for them
    user = UserFactory()
    from orders.models import Cart
    converted = Cart.objects.create(user=user, status=getattr(Cart, 'STATUS_CONVERTED', 'converted'))

    # Auth and merge
    client.force_authenticate(user=user)
    r2 = client.post('/api/carts/merge/', data={'anonymous_cart_uuid': anon_uuid}, format='json')
    assert r2.status_code == 200

    # Ensure an ACTIVE cart exists separate from the converted one
    active = Cart.objects.filter(user=user, status=Cart.STATUS_ACTIVE).first()
    assert active is not None
    assert active.id != converted.id

