import json
import hmac
import hashlib
from decimal import Decimal
from unittest.mock import patch, Mock, MagicMock

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.conf import settings
from django.utils import timezone

from orders.models import Order, OrderItem
from menu.models import MenuItem, MenuCategory
from payments.models import StripePaymentIntent, StripeWebhookEvent
from payments.services import StripePaymentService
from core.models import Table, Organization, Location

User = get_user_model()


class StripeWebhookTestCase(TestCase):
    """Test cases for Stripe webhook processing."""
    
    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.webhook_url = reverse('payments:stripe_webhook')
        
        # Test webhook secret
        self.webhook_secret = 'whsec_test_secret'
        
        self.user = User.objects.create_user(
            username='webhookuser',
            email='webhook@example.com',
            password='testpass123',
            first_name='Webhook',
            last_name='User'
        )
        
        self.organization = Organization.objects.create(
            name='Test Restaurant',
            tax_percent=8.25
        )
        
        self.location = Location.objects.create(
            organization=self.organization,
            name='Main Location',
            timezone='UTC'
        )
        
        self.category = MenuCategory.objects.create(
            organization=self.organization,
            name='Webhook Category'
        )
        
        self.menu_item = MenuItem.objects.create(
            organization=self.organization,
            name='Webhook Item',
            price=Decimal('19.99'),
            category=self.category,
            is_available=True
        )
        
        self.table = Table.objects.create(
            location=self.location,
            table_number='10',
            capacity=4,
            is_active=True
        )
        
        self.order = Order.objects.create(
            user=self.user,
            status='pending',
            delivery_option='DINE_IN',
            dine_in_table=self.table,
            total_amount=Decimal('21.99')
        )
        
        OrderItem.objects.create(
            order=self.order,
            menu_item=self.menu_item,
            quantity=1,
            unit_price=Decimal('19.99')
        )
        
        self.payment_intent = StripePaymentIntent.objects.create(
            order=self.order,
            user=self.user,
            stripe_payment_intent_id='pi_test_webhook_123',
            amount=2199,  # $21.99 in cents
            currency='usd',
            status='requires_payment_method'
        )

    def _create_webhook_signature(self, payload, secret=None):
        """Create a valid Stripe webhook signature."""
        if secret is None:
            secret = self.webhook_secret
        
        timestamp = str(int(timezone.now().timestamp()))
        signed_payload = f"{timestamp}.{payload}"
        
        signature = hmac.new(
            secret.encode('utf-8'),
            signed_payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return f"t={timestamp},v1={signature}"

    def _create_payment_intent_event(self, event_type, payment_intent_id, status='succeeded'):
        """Create a Stripe payment intent event payload."""
        return {
            "id": f"evt_test_{event_type}_{payment_intent_id}",
            "object": "event",
            "api_version": "2020-08-27",
            "created": int(timezone.now().timestamp()),
            "data": {
                "object": {
                    "id": payment_intent_id,
                    "object": "payment_intent",
                    "amount": 2199,
                    "currency": "usd",
                    "status": status,
                    "metadata": {
                        "order_id": str(self.order.id)
                    }
                }
            },
            "livemode": False,
            "pending_webhooks": 1,
            "request": {
                "id": "req_test_123",
                "idempotency_key": None
            },
            "type": event_type
        }

    @patch('payments.views.settings.STRIPE_WEBHOOK_SECRET', 'whsec_test_secret')
    def test_payment_intent_succeeded_webhook(self):
        """Test successful payment intent webhook processing."""
        event_data = self._create_payment_intent_event(
            'payment_intent.succeeded',
            'pi_test_webhook_123'
        )
        
        payload = json.dumps(event_data)
        signature = self._create_webhook_signature(payload)
        
        with patch('payments.tasks.run_post_payment_hooks_task.delay') as mock_task:
            response = self.client.post(
                self.webhook_url,
                data=payload,
                content_type='application/json',
                HTTP_STRIPE_SIGNATURE=signature
            )
        
        self.assertEqual(response.status_code, 200)
        
        # Check that payment intent was updated
        self.payment_intent.refresh_from_db()
        self.assertEqual(self.payment_intent.status, 'succeeded')
        self.assertIsNotNone(self.payment_intent.confirmed_at)
        
        # Check that order was marked as paid
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'paid')
        self.assertIsNotNone(self.order.paid_at)
        
        # Check that webhook event was recorded
        webhook_event = StripeWebhookEvent.objects.get(
            stripe_event_id=event_data['id']
        )
        self.assertEqual(webhook_event.event_type, 'payment_intent.succeeded')
        self.assertTrue(webhook_event.processed)
        
        # Check that post-payment task was triggered
        mock_task.assert_called_once_with(self.order.id)

    @patch('payments.views.settings.STRIPE_WEBHOOK_SECRET', 'whsec_test_secret')
    def test_payment_intent_payment_failed_webhook(self):
        """Test failed payment intent webhook processing."""
        event_data = self._create_payment_intent_event(
            'payment_intent.payment_failed',
            'pi_test_webhook_123',
            status='requires_payment_method'
        )
        
        payload = json.dumps(event_data)
        signature = self._create_webhook_signature(payload)
        
        response = self.client.post(
            self.webhook_url,
            data=payload,
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE=signature
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Check that payment intent status was updated
        self.payment_intent.refresh_from_db()
        self.assertEqual(self.payment_intent.status, 'requires_payment_method')
        
        # Order should remain pending
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'pending')
        self.assertIsNone(self.order.paid_at)

    @patch('payments.views.settings.STRIPE_WEBHOOK_SECRET', 'whsec_test_secret')
    def test_invalid_webhook_signature(self):
        """Test webhook with invalid signature."""
        event_data = self._create_payment_intent_event(
            'payment_intent.succeeded',
            'pi_test_webhook_123'
        )
        
        payload = json.dumps(event_data)
        invalid_signature = "t=123456789,v1=invalid_signature"
        
        response = self.client.post(
            self.webhook_url,
            data=payload,
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE=invalid_signature
        )
        
        self.assertEqual(response.status_code, 400)
        
        # Payment intent should not be updated
        self.payment_intent.refresh_from_db()
        self.assertEqual(self.payment_intent.status, 'requires_payment_method')

    @patch('payments.views.settings.STRIPE_WEBHOOK_SECRET', 'whsec_test_secret')
    def test_duplicate_webhook_event(self):
        """Test handling of duplicate webhook events."""
        event_data = self._create_payment_intent_event(
            'payment_intent.succeeded',
            'pi_test_webhook_123'
        )
        
        # Create existing webhook event
        StripeWebhookEvent.objects.create(
            stripe_event_id=event_data['id'],
            event_type='payment_intent.succeeded',
            processed=True
        )
        
        payload = json.dumps(event_data)
        signature = self._create_webhook_signature(payload)
        
        response = self.client.post(
            self.webhook_url,
            data=payload,
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE=signature
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Should only have one webhook event record
        webhook_events = StripeWebhookEvent.objects.filter(
            stripe_event_id=event_data['id']
        )
        self.assertEqual(webhook_events.count(), 1)

    @patch('payments.views.settings.STRIPE_WEBHOOK_SECRET', 'whsec_test_secret')
    def test_webhook_with_nonexistent_payment_intent(self):
        """Test webhook for non-existent payment intent."""
        event_data = self._create_payment_intent_event(
            'payment_intent.succeeded',
            'pi_nonexistent_123'
        )
        
        payload = json.dumps(event_data)
        signature = self._create_webhook_signature(payload)
        
        response = self.client.post(
            self.webhook_url,
            data=payload,
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE=signature
        )
        
        # Should still return 200 but log the error
        self.assertEqual(response.status_code, 200)
        
        # Webhook event should still be recorded
        webhook_event = StripeWebhookEvent.objects.get(
            stripe_event_id=event_data['id']
        )
        self.assertFalse(webhook_event.processed)

    @patch('payments.views.settings.STRIPE_WEBHOOK_SECRET', 'whsec_test_secret')
    def test_unsupported_webhook_event_type(self):
        """Test handling of unsupported webhook event types."""
        event_data = {
            "id": "evt_test_unsupported_123",
            "object": "event",
            "type": "customer.created",
            "data": {
                "object": {
                    "id": "cus_test_123",
                    "object": "customer"
                }
            }
        }
        
        payload = json.dumps(event_data)
        signature = self._create_webhook_signature(payload)
        
        response = self.client.post(
            self.webhook_url,
            data=payload,
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE=signature
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Webhook event should be recorded but not processed
        webhook_event = StripeWebhookEvent.objects.get(
            stripe_event_id=event_data['id']
        )
        self.assertFalse(webhook_event.processed)

    @patch('payments.views.settings.STRIPE_WEBHOOK_SECRET', 'whsec_test_secret')
    def test_malformed_webhook_payload(self):
        """Test handling of malformed webhook payload."""
        payload = "invalid json payload"
        signature = self._create_webhook_signature(payload)
        
        response = self.client.post(
            self.webhook_url,
            data=payload,
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE=signature
        )
        
        self.assertEqual(response.status_code, 400)

    @patch('payments.views.settings.STRIPE_WEBHOOK_SECRET', 'whsec_test_secret')
    def test_webhook_idempotency(self):
        """Test webhook idempotency handling."""
        event_data = self._create_payment_intent_event(
            'payment_intent.succeeded',
            'pi_test_webhook_123'
        )
        
        payload = json.dumps(event_data)
        signature = self._create_webhook_signature(payload)
        
        # Send webhook twice
        with patch('payments.tasks.run_post_payment_hooks_task.delay') as mock_task:
            response1 = self.client.post(
                self.webhook_url,
                data=payload,
                content_type='application/json',
                HTTP_STRIPE_SIGNATURE=signature
            )
            
            response2 = self.client.post(
                self.webhook_url,
                data=payload,
                content_type='application/json',
                HTTP_STRIPE_SIGNATURE=signature
            )
        
        self.assertEqual(response1.status_code, 200)
        self.assertEqual(response2.status_code, 200)
        
        # Post-payment task should only be called once
        self.assertEqual(mock_task.call_count, 1)
        
        # Should only have one webhook event record
        webhook_events = StripeWebhookEvent.objects.filter(
            stripe_event_id=event_data['id']
        )
        self.assertEqual(webhook_events.count(), 1)


class StripePaymentServiceTestCase(TestCase):
    """Test cases for Stripe payment service."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='serviceuser',
            email='service@example.com',
            password='testpass123'
        )
        
        self.organization = Organization.objects.create(
            name='Service Restaurant',
            tax_percent=8.25
        )
        
        self.location = Location.objects.create(
            organization=self.organization,
            name='Service Location',
            timezone='UTC'
        )
        
        self.category = MenuCategory.objects.create(
            organization=self.organization,
            name='Service Category'
        )
        
        self.menu_item = MenuItem.objects.create(
            organization=self.organization,
            name='Service Item',
            price=Decimal('15.99'),
            category=self.category
        )
        
        self.table = Table.objects.create(
            location=self.location,
            table_number='15',
            capacity=2,
            is_active=True
        )
        
        self.order = Order.objects.create(
            user=self.user,
            status='pending',
            delivery_option='DINE_IN',
            dine_in_table=self.table,
            total_amount=Decimal('17.99')
        )
        
        self.service = StripePaymentService()

    @patch('stripe.PaymentIntent.create')
    def test_create_payment_intent_success(self):
        """Test successful payment intent creation."""
        mock_stripe_pi = Mock()
        mock_stripe_pi.id = 'pi_test_service_123'
        mock_stripe_pi.amount = 1799
        mock_stripe_pi.currency = 'usd'
        mock_stripe_pi.status = 'requires_payment_method'
        mock_stripe_pi.client_secret = 'pi_test_service_123_secret_abc'
        
        stripe.PaymentIntent.create.return_value = mock_stripe_pi
        
        payment_intent = self.service.create_payment_intent(
            order=self.order,
            amount_cents=1799
        )
        
        self.assertIsInstance(payment_intent, StripePaymentIntent)
        self.assertEqual(payment_intent.order, self.order)
        self.assertEqual(payment_intent.stripe_payment_intent_id, 'pi_test_service_123')
        self.assertEqual(payment_intent.amount, 1799)
        self.assertEqual(payment_intent.status, 'requires_payment_method')
        
        # Check Stripe API call
        stripe.PaymentIntent.create.assert_called_once_with(
            amount=1799,
            currency='usd',
            metadata={'order_id': str(self.order.id)},
            automatic_payment_methods={'enabled': True}
        )

    @patch('stripe.PaymentIntent.create')
    def test_create_payment_intent_stripe_error(self):
        """Test payment intent creation with Stripe error."""
        import stripe
        
        stripe.PaymentIntent.create.side_effect = stripe.error.CardError(
            message="Your card was declined.",
            param="card",
            code="card_declined"
        )
        
        with self.assertRaises(stripe.error.CardError):
            self.service.create_payment_intent(
                order=self.order,
                amount_cents=1799
            )

    def test_handle_payment_intent_succeeded(self):
        """Test handling of successful payment intent."""
        payment_intent = StripePaymentIntent.objects.create(
            order=self.order,
            user=self.user,
            stripe_payment_intent_id='pi_test_service_123',
            amount=1799,
            currency='usd',
            status='requires_payment_method'
        )
        
        stripe_data = {
            'id': 'pi_test_service_123',
            'status': 'succeeded',
            'metadata': {'order_id': str(self.order.id)}
        }
        
        with patch('payments.tasks.run_post_payment_hooks_task.delay') as mock_task:
            self.service._handle_payment_intent_succeeded(stripe_data)
        
        # Check payment intent was updated
        payment_intent.refresh_from_db()
        self.assertEqual(payment_intent.status, 'succeeded')
        self.assertIsNotNone(payment_intent.confirmed_at)
        
        # Check order was marked as paid
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'paid')
        self.assertIsNotNone(self.order.paid_at)
        
        # Check post-payment task was triggered
        mock_task.assert_called_once_with(self.order.id)

    def test_handle_payment_intent_succeeded_nonexistent_order(self):
        """Test handling payment intent with non-existent order."""
        stripe_data = {
            'id': 'pi_test_service_123',
            'status': 'succeeded',
            'metadata': {'order_id': '99999'}  # Non-existent order
        }
        
        # Should not raise exception
        self.service._handle_payment_intent_succeeded(stripe_data)

    def test_handle_payment_intent_payment_failed(self):
        """Test handling of failed payment intent."""
        payment_intent = StripePaymentIntent.objects.create(
            order=self.order,
            user=self.user,
            stripe_payment_intent_id='pi_test_service_123',
            amount=1799,
            currency='usd',
            status='requires_payment_method'
        )
        
        stripe_data = {
            'id': 'pi_test_service_123',
            'status': 'requires_payment_method',
            'last_payment_error': {
                'message': 'Your card was declined.'
            }
        }
        
        self.service._handle_payment_intent_payment_failed(stripe_data)
        
        # Payment intent should be updated but order should remain pending
        payment_intent.refresh_from_db()
        self.assertEqual(payment_intent.status, 'requires_payment_method')
        
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'pending')
        self.assertIsNone(self.order.paid_at)


class WebhookIntegrationTestCase(TestCase):
    """Integration tests for webhook processing."""
    
    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.webhook_url = reverse('payments:stripe_webhook')
        
        self.user = User.objects.create_user(
            username='integrationuser',
            email='integration@example.com',
            password='testpass123'
        )
        
        self.organization = Organization.objects.create(
            name='Integration Restaurant',
            tax_percent=8.25
        )
        
        self.location = Location.objects.create(
            organization=self.organization,
            name='Integration Location',
            timezone='UTC'
        )
        
        self.category = MenuCategory.objects.create(
            organization=self.organization,
            name='Integration Category'
        )
        
        self.menu_item = MenuItem.objects.create(
            organization=self.organization,
            name='Integration Item',
            price=Decimal('29.99'),
            category=self.category
        )
        
        self.table = Table.objects.create(
            location=self.location,
            table_number='20',
            capacity=6,
            is_active=True
        )
        
        self.order = Order.objects.create(
            user=self.user,
            status='pending',
            delivery_option='DINE_IN',
            dine_in_table=self.table,
            total_amount=Decimal('32.99')
        )
        
        OrderItem.objects.create(
            order=self.order,
            menu_item=self.menu_item,
            quantity=1,
            unit_price=Decimal('29.99')
        )

    @patch('payments.views.settings.STRIPE_WEBHOOK_SECRET', 'whsec_integration_test')
    @patch('payments.tasks.run_post_payment_hooks_task.delay')
    def test_end_to_end_webhook_processing(self, mock_task):
        """Test complete webhook processing flow."""
        # Create payment intent
        payment_intent = StripePaymentIntent.objects.create(
            order=self.order,
            user=self.user,
            stripe_payment_intent_id='pi_integration_test_123',
            amount=3299,
            currency='usd',
            status='requires_payment_method'
        )
        
        # Create webhook event
        event_data = {
            "id": "evt_integration_test_123",
            "object": "event",
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": "pi_integration_test_123",
                    "object": "payment_intent",
                    "amount": 3299,
                    "currency": "usd",
                    "status": "succeeded",
                    "metadata": {
                        "order_id": str(self.order.id)
                    }
                }
            }
        }
        
        payload = json.dumps(event_data)
        
        # Create signature
        timestamp = str(int(timezone.now().timestamp()))
        signed_payload = f"{timestamp}.{payload}"
        signature = hmac.new(
            'whsec_integration_test'.encode('utf-8'),
            signed_payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        stripe_signature = f"t={timestamp},v1={signature}"
        
        # Send webhook
        response = self.client.post(
            self.webhook_url,
            data=payload,
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE=stripe_signature
        )
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        
        # Verify payment intent was updated
        payment_intent.refresh_from_db()
        self.assertEqual(payment_intent.status, 'succeeded')
        self.assertIsNotNone(payment_intent.confirmed_at)
        
        # Verify order was updated
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'paid')
        self.assertIsNotNone(self.order.paid_at)
        
        # Verify webhook event was recorded
        webhook_event = StripeWebhookEvent.objects.get(
            stripe_event_id='evt_integration_test_123'
        )
        self.assertTrue(webhook_event.processed)
        
        # Verify post-payment processing was triggered
        mock_task.assert_called_once_with(self.order.id)