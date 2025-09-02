import pytest
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.core import mail
from celery.exceptions import Retry

from orders.models import Order, OrderItem
from menu.models import MenuItem, MenuCategory
from payments.tasks import (
    run_post_payment_hooks_task,
    send_order_confirmation_email_task,
    send_staff_notification_task,
    sync_order_to_pos_task,
    record_payment_analytics_task,
    process_loyalty_rewards_task,
    update_inventory_levels_task,
)
from payments.models import StripePaymentIntent

User = get_user_model()


class CeleryTaskTestCase(TestCase):
    """Base test case for Celery tasks with common setup."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
        
        self.category = MenuCategory.objects.create(
            name='Test Category',
            description='Test category description'
        )
        
        self.menu_item = MenuItem.objects.create(
            name='Test Item',
            description='Test item description',
            price=Decimal('12.99'),
            category=self.category,
            is_available=True
        )
        
        self.order = Order.objects.create(
            user=self.user,
            status='pending',
            total=Decimal('15.99'),
            customer_name='Test User',
            customer_email='test@example.com',
            service_type='dine_in'
        )
        
        self.order_item = OrderItem.objects.create(
            order=self.order,
            menu_item=self.menu_item,
            quantity=1,
            unit_price=Decimal('12.99'),
            total_price=Decimal('12.99')
        )
        
        self.payment_intent = StripePaymentIntent.objects.create(
            order=self.order,
            user=self.user,
            stripe_payment_intent_id='pi_test123',
            amount=1599,
            currency='usd',
            status='succeeded'
        )


class TestPostPaymentHooksTask(CeleryTaskTestCase):
    """Test the main post-payment hooks orchestration task."""
    
    @patch('payments.post_payment.run_post_payment_hooks')
    def test_run_post_payment_hooks_task_success(self, mock_run_hooks):
        """Test successful execution of post-payment hooks task."""
        # Execute task
        result = run_post_payment_hooks_task.apply(args=[self.order.id])
        
        # Verify task completed successfully
        self.assertTrue(result.successful())
        mock_run_hooks.assert_called_once_with(self.order)
    
    def test_run_post_payment_hooks_task_order_not_found(self):
        """Test task behavior when order doesn't exist."""
        # Execute task with non-existent order ID
        result = run_post_payment_hooks_task.apply(args=[99999])
        
        # Verify task failed gracefully
        self.assertFalse(result.successful())
        self.assertIn('Order not found', str(result.result))
    
    @patch('payments.post_payment.run_post_payment_hooks')
    def test_run_post_payment_hooks_task_exception_handling(self, mock_run_hooks):
        """Test task handles exceptions properly."""
        mock_run_hooks.side_effect = Exception('Test error')
        
        # Execute task
        result = run_post_payment_hooks_task.apply(args=[self.order.id])
        
        # Verify task failed but didn't crash
        self.assertFalse(result.successful())
        self.assertIn('Test error', str(result.result))


class TestEmailTasks(CeleryTaskTestCase):
    """Test email-related Celery tasks."""
    
    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_send_order_confirmation_email_task_success(self):
        """Test successful order confirmation email sending."""
        # Execute task
        result = send_order_confirmation_email_task.apply(
            args=[self.order.id, 'test@example.com']
        )
        
        # Verify task completed successfully
        self.assertTrue(result.successful())
        
        # Verify email was sent
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertIn('Order Confirmation', email.subject)
        self.assertEqual(email.to, ['test@example.com'])
    
    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_send_staff_notification_task_success(self):
        """Test successful staff notification email sending."""
        # Execute task
        result = send_staff_notification_task.apply(
            args=[self.order.id, ['staff@example.com']]
        )
        
        # Verify task completed successfully
        self.assertTrue(result.successful())
        
        # Verify email was sent
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertIn('New Order Alert', email.subject)
        self.assertEqual(email.to, ['staff@example.com'])
    
    def test_send_order_confirmation_email_task_order_not_found(self):
        """Test email task behavior when order doesn't exist."""
        result = send_order_confirmation_email_task.apply(
            args=[99999, 'test@example.com']
        )
        
        self.assertFalse(result.successful())
        self.assertIn('Order not found', str(result.result))
    
    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    @patch('payments.tasks.send_mail')
    def test_send_order_confirmation_email_task_retry_on_failure(self, mock_send_mail):
        """Test email task retries on failure."""
        mock_send_mail.side_effect = Exception('SMTP error')
        
        # Execute task
        result = send_order_confirmation_email_task.apply(
            args=[self.order.id, 'test@example.com']
        )
        
        # Verify task failed after retries
        self.assertFalse(result.successful())
        self.assertIn('SMTP error', str(result.result))


class TestPOSSyncTask(CeleryTaskTestCase):
    """Test POS synchronization task."""
    
    @patch('payments.tasks._sync_to_square_pos')
    def test_sync_order_to_pos_task_square_success(self, mock_sync_square):
        """Test successful Square POS synchronization."""
        mock_sync_square.return_value = {'success': True, 'pos_order_id': 'sq_123'}
        
        # Execute task
        result = sync_order_to_pos_task.apply(
            args=[self.order.id, 'square']
        )
        
        # Verify task completed successfully
        self.assertTrue(result.successful())
        mock_sync_square.assert_called_once_with(self.order)
    
    @patch('payments.tasks._sync_to_toast_pos')
    def test_sync_order_to_pos_task_toast_success(self, mock_sync_toast):
        """Test successful Toast POS synchronization."""
        mock_sync_toast.return_value = {'success': True, 'pos_order_id': 'toast_456'}
        
        # Execute task
        result = sync_order_to_pos_task.apply(
            args=[self.order.id, 'toast']
        )
        
        # Verify task completed successfully
        self.assertTrue(result.successful())
        mock_sync_toast.assert_called_once_with(self.order)
    
    def test_sync_order_to_pos_task_unsupported_pos(self):
        """Test task behavior with unsupported POS system."""
        result = sync_order_to_pos_task.apply(
            args=[self.order.id, 'unsupported_pos']
        )
        
        self.assertFalse(result.successful())
        self.assertIn('Unsupported POS system', str(result.result))
    
    @patch('payments.tasks._sync_to_square_pos')
    def test_sync_order_to_pos_task_retry_on_failure(self, mock_sync_square):
        """Test POS sync task retries on failure."""
        mock_sync_square.side_effect = Exception('POS API error')
        
        # Execute task
        result = sync_order_to_pos_task.apply(
            args=[self.order.id, 'square']
        )
        
        # Verify task failed after retries
        self.assertFalse(result.successful())
        self.assertIn('POS API error', str(result.result))


class TestAnalyticsTask(CeleryTaskTestCase):
    """Test analytics recording task."""
    
    @patch('payments.tasks.logger')
    def test_record_payment_analytics_task_success(self, mock_logger):
        """Test successful analytics recording."""
        # Execute task
        result = record_payment_analytics_task.apply(
            args=[self.order.id, {'payment_method': 'stripe', 'amount': 1599}]
        )
        
        # Verify task completed successfully
        self.assertTrue(result.successful())
        
        # Verify analytics were logged
        mock_logger.info.assert_called()
        log_call_args = mock_logger.info.call_args[0][0]
        self.assertIn('Payment analytics recorded', log_call_args)
    
    def test_record_payment_analytics_task_order_not_found(self):
        """Test analytics task behavior when order doesn't exist."""
        result = record_payment_analytics_task.apply(
            args=[99999, {'payment_method': 'stripe'}]
        )
        
        self.assertFalse(result.successful())
        self.assertIn('Order not found', str(result.result))


class TestLoyaltyTask(CeleryTaskTestCase):
    """Test loyalty rewards processing task."""
    
    @patch('payments.tasks.logger')
    def test_process_loyalty_rewards_task_success(self, mock_logger):
        """Test successful loyalty rewards processing."""
        # Execute task
        result = process_loyalty_rewards_task.apply(
            args=[self.order.id]
        )
        
        # Verify task completed successfully
        self.assertTrue(result.successful())
        
        # Verify loyalty processing was logged
        mock_logger.info.assert_called()
        log_call_args = mock_logger.info.call_args[0][0]
        self.assertIn('Loyalty rewards processed', log_call_args)
    
    def test_process_loyalty_rewards_task_order_not_found(self):
        """Test loyalty task behavior when order doesn't exist."""
        result = process_loyalty_rewards_task.apply(
            args=[99999]
        )
        
        self.assertFalse(result.successful())
        self.assertIn('Order not found', str(result.result))


class TestInventoryTask(CeleryTaskTestCase):
    """Test inventory update task."""
    
    @patch('payments.tasks.logger')
    def test_update_inventory_levels_task_success(self, mock_logger):
        """Test successful inventory level updates."""
        # Execute task
        result = update_inventory_levels_task.apply(
            args=[self.order.id]
        )
        
        # Verify task completed successfully
        self.assertTrue(result.successful())
        
        # Verify inventory update was logged
        mock_logger.info.assert_called()
        log_call_args = mock_logger.info.call_args[0][0]
        self.assertIn('Inventory levels updated', log_call_args)
    
    def test_update_inventory_levels_task_order_not_found(self):
        """Test inventory task behavior when order doesn't exist."""
        result = update_inventory_levels_task.apply(
            args=[99999]
        )
        
        self.assertFalse(result.successful())
        self.assertIn('Order not found', str(result.result))


class TestTaskIntegration(CeleryTaskTestCase):
    """Test task integration and workflow."""
    
    @patch('payments.post_payment.run_post_payment_hooks')
    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_complete_post_payment_workflow(self, mock_run_hooks):
        """Test complete post-payment processing workflow."""
        # Mock the post-payment hooks to trigger async tasks
        def mock_hooks_implementation(order):
            # Simulate triggering async tasks
            send_order_confirmation_email_task.delay(order.id, order.customer_email)
            send_staff_notification_task.delay(order.id, ['staff@example.com'])
            sync_order_to_pos_task.delay(order.id, 'square')
            record_payment_analytics_task.delay(order.id, {'payment_method': 'stripe'})
            process_loyalty_rewards_task.delay(order.id)
            update_inventory_levels_task.delay(order.id)
        
        mock_run_hooks.side_effect = mock_hooks_implementation
        
        # Execute main task
        result = run_post_payment_hooks_task.apply(args=[self.order.id])
        
        # Verify main task completed
        self.assertTrue(result.successful())
        mock_run_hooks.assert_called_once_with(self.order)
    
    def test_task_error_handling_and_logging(self):
        """Test that tasks handle errors gracefully and log appropriately."""
        with patch('payments.tasks.logger') as mock_logger:
            # Test with invalid order ID
            result = send_order_confirmation_email_task.apply(
                args=[99999, 'test@example.com']
            )
            
            # Verify error was logged
            self.assertFalse(result.successful())
            mock_logger.error.assert_called()