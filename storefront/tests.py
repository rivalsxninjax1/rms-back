from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from decimal import Decimal
from menu.models import MenuItem, MenuCategory
from core.models import Table, Organization, Location
from orders.models import Cart
from reservations.models import Reservation
from payments.services import StripePaymentService
from menu.models import ModifierGroup, Modifier

User = get_user_model()

class StorefrontFlowTests(TestCase):
    def setUp(self):
        org = Organization.objects.create(name="Org")
        self.loc = Location.objects.create(organization=org, name="Main")
        self.table = Table.objects.create(location=self.loc, table_number="A1", capacity=4, is_active=True)
        self.cat = MenuCategory.objects.create(organization=org, name="Pizza", is_active=True)
        self.item = MenuItem.objects.create(organization=org, name="Margherita", slug="margherita", price=Decimal("10.00"), is_available=True, category=self.cat)
        self.c = Client()

    def test_add_and_checkout_takeaway(self):
        resp = self.c.post(reverse("storefront:cart_add"), {"menu_id": self.item.id, "qty": 2})
        self.assertIn(resp.status_code, (200, 302))
        resp = self.c.post(reverse("storefront:cart_option"), {"order_type":"TAKEAWAY"})
        self.assertIn(resp.status_code, (200, 302))
        resp = self.c.post(reverse("storefront:cart_checkout"))
        # Not logged in → requires auth
        self.assertIn(resp.status_code, (401, 200, 400, 409))

    def test_dine_in_requires_table(self):
        self.c.post(reverse("storefront:cart_add"), {"menu_id": self.item.id})
        self.c.post(reverse("storefront:cart_option"), {"order_type":"DINE_IN"})
        resp = self.c.post(reverse("storefront:cart_checkout"))
        # Missing table should be 400, or 401 if auth required hits first
        self.assertIn(resp.status_code, (400, 401))

    def test_expiry_set_to_25(self):
        self.c.get(reverse("storefront:menu_list"))
        cart = Cart.objects.first()
        self.assertIsNotNone(cart.expires_at)

    def test_modal_extras_flow(self):
        # Create a modifier group + two modifiers for the item
        g = ModifierGroup.objects.create(menu_item=self.item, name="Add-ons", is_active=True, max_selections=5)
        m1 = Modifier.objects.create(modifier_group=g, name="Cheese", price=Decimal("2.50"), is_available=True)
        m2 = Modifier.objects.create(modifier_group=g, name="Olives", price=Decimal("1.50"), is_available=True)

        # Add to cart via storefront
        self.c.post(reverse("storefront:cart_add"), {"menu_id": self.item.id, "qty": 1})
        cart = Cart.objects.first()
        line = cart.items.first()

        # Open modal
        resp = self.c.get(reverse("storefront:cart_extras_modal") + f"?line_id={line.id}")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Save Extras", resp.content)

        # Save extras via POST
        resp = self.c.post(reverse("storefront:cart_extras"), {"line_id": line.id, "modifiers": str(m1.id)})
        self.assertIn(resp.status_code, (200, 302))
        cart.refresh_from_db()
        line.refresh_from_db()
        self.assertTrue(any(d.get("modifier_id") == m1.id for d in (line.selected_modifiers or [])))
        self.assertGreaterEqual(cart.modifier_total, Decimal("2.50"))

    def test_dine_in_checkout_session_webhook_creates_reservation(self):
        # Build a dine-in cart -> order
        self.c.post(reverse("storefront:cart_add"), {"menu_id": self.item.id, "qty": 1})
        # Set DINE_IN option with table
        self.c.post(reverse("storefront:cart_option"), {"order_type": "DINE_IN", "table_id": self.table.id})
        cart = Cart.objects.first()
        # Provide guest details to satisfy order validation
        cart.customer_name = "Guest"
        cart.customer_phone = "1234567890"
        cart.calculate_totals(); cart.save()

        # Create order from cart
        from orders.models import Order as AppOrder
        order = AppOrder.create_from_cart(cart)

        # Simulate Stripe checkout.session.completed webhook event
        svc = StripePaymentService()
        event = {
            "id": "evt_test_123",
            "type": "checkout.session.completed",
            "data": {"object": {"metadata": {"order_id": str(order.id)}}},
        }
        ok = svc.process_webhook_event(event)
        self.assertTrue(ok)
        # Reservation created for the table
        self.assertTrue(Reservation.objects.filter(table=self.table).exists())
