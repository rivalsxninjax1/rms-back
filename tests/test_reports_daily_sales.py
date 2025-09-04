import pytest
from decimal import Decimal
from django.utils import timezone


@pytest.mark.django_db
def test_daily_sales_payments_breakdown(api_client, user):
    from orders.models import Order
    from billing.models import Payment
    from engagement.models import OrderExtras

    today = timezone.localdate()

    # Order 1 (cash) with tip and coupon
    o1 = Order.objects.create(user=user, total_amount=Decimal('25.00'))
    OrderExtras.objects.create(order=o1, name='tip', amount=Decimal('3.00'))
    OrderExtras.objects.create(order=o1, name='coupon_discount', amount=Decimal('2.00'))
    Payment.objects.create(order=o1, amount=Decimal('25.00'), currency='USD', method='cash', status='captured')

    # Order 2 (stripe) with loyalty
    o2 = Order.objects.create(user=user, total_amount=Decimal('40.00'))
    OrderExtras.objects.create(order=o2, name='loyalty_discount', amount=Decimal('5.00'))
    Payment.objects.create(order=o2, amount=Decimal('40.00'), currency='USD', method='stripe', status='captured')

    # Order 3 (pos_card) no extras
    o3 = Order.objects.create(user=user, total_amount=Decimal('10.00'))
    Payment.objects.create(order=o3, amount=Decimal('10.00'), currency='USD', method='pos_card', status='captured')

    # Query today's payments breakdown
    resp = api_client.get(f'/api/reports/daily-sales/payments?date_from={today.isoformat()}&date_to={today.isoformat()}')
    assert resp.status_code == 200
    data = resp.json().get('results') or []

    # Convert to dict by method for easier assertions
    by_method = {}
    for row in data:
        by_method[row['method']] = row

    # Totals per method
    assert float(by_method['cash']['total']) == 25.0
    assert float(by_method['stripe']['total']) == 40.0
    assert float(by_method['pos_card']['total']) == 10.0

    # Extras aggregated
    assert float(by_method['cash']['tip']) == 3.0
    assert float(by_method['cash']['coupon']) == 2.0
    assert float(by_method['stripe']['loyalty']) == 5.0
    assert float(by_method['pos_card'].get('tip', 0)) == 0.0

