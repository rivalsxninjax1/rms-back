# FILE: payments/tasks.py
from __future__ import annotations
import logging
from typing import Optional, Dict, Any

from django.apps import apps
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone

logger = logging.getLogger(__name__)

try:
    from celery import shared_task
except Exception:  # Celery not installed; provide a no-op decorator
    def shared_task(*d, **kw):
        def _wrap(fn):
            return fn
        return _wrap

@shared_task
def run_post_payment_hooks_task(order_id: int):
    """
    Celery task wrapper for post-payment hooks.
    This file is safe even if Celery isn't installed (no-op decorator).
    """
    try:
        Order = apps.get_model("orders", "Order")
        order = Order.objects.filter(pk=order_id).first()
        if not order:
            return
        from payments.post_payment import run_post_payment_hooks
        run_post_payment_hooks(order, payment=getattr(order, "payment", None))
    except Exception:
        logger.exception("run_post_payment_hooks_task failed for order %s", order_id)

@shared_task
def send_order_confirmation_email_task(order_id: int):
    """
    Send order confirmation email to customer.
    """
    try:
        Order = apps.get_model("orders", "Order")
        order = Order.objects.filter(pk=order_id).first()
        if not order:
            return
        
        recipient_email = None
        if hasattr(order, 'email') and order.email:
            recipient_email = order.email
        elif hasattr(order, 'user') and order.user and order.user.email:
            recipient_email = order.user.email
        
        if not recipient_email:
            logger.warning(f"No email available for order {order_id}")
            return
        
        context = {
            'order': order,
            'order_items': order.items.all() if hasattr(order, 'items') else [],
            'restaurant_name': getattr(settings, 'RESTAURANT_NAME', 'Restaurant'),
            'support_email': getattr(settings, 'SUPPORT_EMAIL', 'support@restaurant.com'),
        }
        
        subject = f"Order Confirmation #{getattr(order, 'order_number', order.id)}"
        
        # Try to use templates if they exist, otherwise use simple text
        try:
            html_message = render_to_string('emails/order_confirmation.html', context)
            plain_message = render_to_string('emails/order_confirmation.txt', context)
        except Exception:
            # Fallback to simple text message
            plain_message = f"Thank you for your order #{getattr(order, 'order_number', order.id)}!\n\nYour order has been confirmed and is being prepared.\n\nTotal: ${order.total}\n\nThank you for choosing {context['restaurant_name']}!"
            html_message = None
        
        send_mail(
            subject=subject,
            message=plain_message,
            html_message=html_message,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@restaurant.com'),
            recipient_list=[recipient_email],
            fail_silently=False,
        )
        
        logger.info(f"Order confirmation email sent for order {order_id}")
        
    except Exception:
        logger.exception(f"Failed to send confirmation email for order {order_id}")

@shared_task
def send_staff_notification_task(order_id: int):
    """
    Send new order notification to restaurant staff.
    """
    try:
        staff_emails = getattr(settings, 'STAFF_NOTIFICATION_EMAILS', [])
        if not staff_emails:
            return
        
        Order = apps.get_model("orders", "Order")
        order = Order.objects.filter(pk=order_id).first()
        if not order:
            return
        
        context = {
            'order': order,
            'order_items': order.items.all() if hasattr(order, 'items') else [],
            'customer_name': getattr(order, 'customer_name', 'Guest'),
            'order_time': order.created_at,
        }
        
        subject = f"New Order #{getattr(order, 'order_number', order.id)} - {getattr(order, 'service_type', 'Dine-in')}"
        
        try:
            html_message = render_to_string('emails/staff_notification.html', context)
            plain_message = render_to_string('emails/staff_notification.txt', context)
        except Exception:
            # Fallback to simple text message
            items_text = "\n".join([f"- {item.menu_item.name} x {item.quantity}" for item in context['order_items']])
            plain_message = f"New Order #{getattr(order, 'order_number', order.id)}\n\nCustomer: {context['customer_name']}\nService: {getattr(order, 'service_type', 'Dine-in')}\nTotal: ${order.total}\n\nItems:\n{items_text}"
            html_message = None
        
        send_mail(
            subject=subject,
            message=plain_message,
            html_message=html_message,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@restaurant.com'),
            recipient_list=staff_emails,
            fail_silently=False,
        )
        
        logger.info(f"Staff notification email sent for order {order_id}")
        
    except Exception:
        logger.exception(f"Failed to send staff notification for order {order_id}")

@shared_task
def sync_order_to_pos_task(order_id: int):
    """
    Sync order to POS system.
    """
    try:
        pos_enabled = getattr(settings, 'POS_INTEGRATION_ENABLED', False)
        if not pos_enabled:
            return
        
        Order = apps.get_model("orders", "Order")
        order = Order.objects.filter(pk=order_id).first()
        if not order:
            return
        
        pos_system = getattr(settings, 'POS_SYSTEM', None)
        
        if pos_system == 'square':
            _sync_to_square_pos(order)
        elif pos_system == 'toast':
            _sync_to_toast_pos(order)
        elif pos_system == 'clover':
            _sync_to_clover_pos(order)
        else:
            logger.info(f"No POS integration configured for system: {pos_system}")
        
        logger.info(f"Order {order_id} synced to POS system: {pos_system}")
        
    except Exception:
        logger.exception(f"Failed to sync order {order_id} to POS")

@shared_task
def record_payment_analytics_task(order_id: int, payment_data: Optional[Dict[str, Any]] = None):
    """
    Record payment analytics event.
    """
    try:
        Order = apps.get_model("orders", "Order")
        order = Order.objects.filter(pk=order_id).first()
        if not order:
            return
        
        # Try to get analytics model if it exists
        try:
            PaymentAnalytics = apps.get_model('analytics', 'PaymentAnalytics')
            
            analytics_data = {
                'order_id': order.id,
                'amount': order.total,
                'currency': getattr(order, 'currency', 'USD'),
                'payment_method': payment_data.get('payment_method_type', 'unknown') if payment_data else 'unknown',
                'service_type': getattr(order, 'service_type', 'dine_in'),
                'customer_type': 'registered' if getattr(order, 'user', None) else 'guest',
                'order_items_count': order.items.count() if hasattr(order, 'items') else 0,
                'created_at': timezone.now(),
            }
            
            PaymentAnalytics.objects.create(**analytics_data)
            logger.info(f"Analytics recorded for order {order_id}")
            
        except (LookupError, ImportError):
            # Fallback to simple logging-based analytics
            analytics_info = {
                'event': 'payment_completed',
                'order_id': order.id,
                'amount': str(order.total),
                'timestamp': timezone.now().isoformat(),
                'service_type': getattr(order, 'service_type', 'unknown'),
            }
            logger.info(f"Payment analytics: {analytics_info}")
        
    except Exception:
        logger.exception(f"Failed to record analytics for order {order_id}")

@shared_task
def process_loyalty_rewards_task(order_id: int):
    """
    Process loyalty points and rewards for the order.
    """
    try:
        Order = apps.get_model("orders", "Order")
        order = Order.objects.filter(pk=order_id).first()
        if not order:
            return
        
        user = getattr(order, 'user', None)
        if not user:
            return  # No loyalty for guest orders
        
        try:
            # Try to get loyalty models
            LoyaltyAccount = apps.get_model('loyality', 'LoyaltyAccount')  # Note: typo in app name
            LoyaltyTransaction = apps.get_model('loyality', 'LoyaltyTransaction')
            
            # Get or create loyalty account
            loyalty_account, created = LoyaltyAccount.objects.get_or_create(
                user=user,
                defaults={'points_balance': 0}
            )
            
            # Calculate points (e.g., 1 point per dollar spent)
            points_earned = int(float(order.total))  # Simple 1:1 ratio
            
            # Award points
            from django.db import transaction
            with transaction.atomic():
                loyalty_account.points_balance += points_earned
                loyalty_account.save()
                
                # Record transaction
                LoyaltyTransaction.objects.create(
                    account=loyalty_account,
                    transaction_type='earned',
                    points=points_earned,
                    order=order,
                    description=f'Points earned from order #{getattr(order, "order_number", order.id)}'
                )
            
            logger.info(f"Awarded {points_earned} loyalty points to user {user.id} for order {order_id}")
            
        except (LookupError, ImportError):
            logger.info(f"Loyalty system not available for order {order_id}")
        
    except Exception:
        logger.exception(f"Failed to process loyalty rewards for order {order_id}")

@shared_task
def update_inventory_levels_task(order_id: int):
    """
    Update inventory levels based on order items.
    """
    try:
        Order = apps.get_model("orders", "Order")
        order = Order.objects.filter(pk=order_id).first()
        if not order or not hasattr(order, 'items'):
            return
        
        try:
            InventoryItem = apps.get_model('inventory', 'InventoryItem')
        except (LookupError, ImportError):
            logger.info(f"Inventory system not available for order {order_id}")
            return
        
        # Update inventory for each order item
        from django.db import transaction
        for order_item in order.items.all():
            menu_item = order_item.menu_item
            quantity = order_item.quantity
            
            # Try to find corresponding inventory item
            try:
                inventory_item = InventoryItem.objects.get(menu_item=menu_item)
                
                with transaction.atomic():
                    if inventory_item.quantity >= quantity:
                        inventory_item.quantity -= quantity
                        inventory_item.save()
                        logger.info(f"Updated inventory for {menu_item.name}: -{quantity}")
                    else:
                        logger.warning(f"Insufficient inventory for {menu_item.name}")
                        
            except InventoryItem.DoesNotExist:
                logger.info(f"No inventory tracking for menu item: {menu_item.name}")
        
    except Exception:
        logger.exception(f"Failed to update inventory for order {order_id}")

# POS Integration Helper Functions
def _sync_to_square_pos(order):
    """Sync order to Square POS system."""
    # Placeholder for Square POS integration
    # This would use Square's API to create orders in their system
    logger.info(f"Would sync order {order.id} to Square POS")

def _sync_to_toast_pos(order):
    """Sync order to Toast POS system."""
    # Placeholder for Toast POS integration
    # This would use Toast's API to create orders in their system
    logger.info(f"Would sync order {order.id} to Toast POS")

def _sync_to_clover_pos(order):
    """Sync order to Clover POS system."""
    # Placeholder for Clover POS integration
    # This would use Clover's API to create orders in their system
    logger.info(f"Would sync order {order.id} to Clover POS")
