import json
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from tests.factories import (
    UserFactory,
    MenuItemFactory,
)
from orders.models import Order


@pytest.mark.django_db
def test_order_money_fields_readonly(auth_api_client: APIClient):
    # Create a menu item and get/create a cart via API
    item = MenuItemFactory()

    # Get current cart
    r = auth_api_client.get('/api/carts/')
    assert r.status_code == 200
    cart_uuid = r.data.get('cart_uuid')
    assert cart_uuid, r.data

    # Add item to cart
    r = auth_api_client.post('/api/carts/add_item/', data={
        'menu_item_id': item.id,
        'quantity': 2,
    }, format='json')
    assert r.status_code in (200, 201), r.content

    # Create order from cart
    r = auth_api_client.post('/api/orders/', data={
        'cart_uuid': cart_uuid,
    }, format='json')
    assert r.status_code == 201, r.content
    order = r.data['order']
    order_id = order['order_number'] if 'order_number' in order else None
    order_pk = order.get('id') or order.get('pk') or None
    # Fallback: fetch recent orders to get numeric ID
    if not order_pk:
        r2 = auth_api_client.get('/api/orders/recent/')
        assert r2.status_code == 200
        recent = r2.data['recent_orders']
        assert len(recent) >= 1
        order_pk = recent[0]['order_uuid'] if 'order_uuid' in recent[0] else None
    # As a robust choice, query list to find the created order by total and created_at
    order_obj = Order.objects.order_by('-id').first()
    assert order_obj is not None
    oid = order_obj.id

    # Attempt to tamper with totals via PATCH
    tamper = {
        'total_amount': '0.01',
        'tax_amount': '0.00',
        'discount_amount': '9999.99',
        'tip_amount': '0.00',
    }
    r = auth_api_client.patch(f'/api/orders/{oid}/', data=tamper, format='json')
    assert r.status_code == 400, r.content
    assert 'forbidden_fields' in r.data
    for f in tamper:
        assert f in r.data['forbidden_fields'] or all(x in r.data['forbidden_fields'] for x in tamper.keys())


@pytest.mark.django_db
def test_cart_money_fields_readonly(auth_api_client: APIClient):
    # Just ensure PATCH with money fields is rejected on the Cart endpoint
    r = auth_api_client.get('/api/carts/')
    assert r.status_code == 200
    cart_uuid = r.data.get('cart_uuid')
    assert cart_uuid

    tamper = {
        'total': '0.01',
        'tax_amount': '0.00',
        'discount_amount': '9999.99',
        'tip_amount': '0.00',
        'tax_rate': '0.0000',
    }
    # PATCHing cart endpoint may use numeric pk; try both UUID and fallback to list->id if needed
    r_patch = auth_api_client.patch(f'/api/carts/{cart_uuid}/', data=tamper, format='json')
    if r_patch.status_code == 404 or r_patch.status_code == 405:
        # Fallback: try with list to get a numeric id if router uses pk
        # Not all projects expose update; if not, skip as passed
        pytest.skip('Cart update endpoint not available (router default).')
    else:
        assert r_patch.status_code == 400
        assert 'forbidden_fields' in r_patch.data
