from __future__ import annotations

import json
from typing import Any, Dict

from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import get_user_model
from django.core.serializers.json import DjangoJSONEncoder

from orders.models import Order, OrderItem
from menu.models import MenuItem, MenuCategory, Modifier, ModifierGroup
from django.contrib.auth import get_user_model

User = get_user_model()
from .models import AuditLog

User = get_user_model()

# Models to track for audit logging
TRACKED_MODELS = [
    Order, OrderItem, MenuItem, MenuCategory, Modifier, ModifierGroup, User
]

# Store original values before save
_original_values = {}


@receiver(pre_save)
def store_original_values(sender, instance, **kwargs):
    """Store original values before save to track changes."""
    if sender in TRACKED_MODELS and instance.pk:
        try:
            original = sender.objects.get(pk=instance.pk)
            _original_values[f"{sender.__name__}_{instance.pk}"] = {
                field.name: getattr(original, field.name)
                for field in sender._meta.fields
                if hasattr(original, field.name)
            }
        except sender.DoesNotExist:
            pass


@receiver(post_save)
def log_model_save(sender, instance, created, **kwargs):
    """Log model creation and updates."""
    if sender in TRACKED_MODELS:
        # Skip logging for AuditLog itself to avoid infinite loops
        if sender == AuditLog:
            return
            
        try:
            # Get current user from thread local storage if available
            user = getattr(instance, '_audit_user', None)
            if not user:
                # Try to get from request context (if middleware is used)
                from threading import current_thread
                user = getattr(current_thread(), 'user', None)
            
            # Skip if no user context (e.g., system operations)
            if not user or not hasattr(user, 'is_staff') or not user.is_staff:
                return
            
            content_type = ContentType.objects.get_for_model(sender)
            action = 'create' if created else 'update'
            
            # Prepare changes data
            changes = {}
            if not created:
                # Track what changed
                original_key = f"{sender.__name__}_{instance.pk}"
                if original_key in _original_values:
                    original = _original_values[original_key]
                    for field_name, original_value in original.items():
                        current_value = getattr(instance, field_name, None)
                        if original_value != current_value:
                            changes[field_name] = {
                                'from': original_value,
                                'to': current_value
                            }
                    # Clean up stored values
                    del _original_values[original_key]
            
            # Create audit log entry
            AuditLog.objects.create(
                user=user,
                action=action,
                description=f"{action.title()} {sender.__name__}: {str(instance)}",
                content_type=content_type,
                object_id=str(instance.pk),
                object_repr=str(instance),
                model_name=sender.__name__,
                changes=changes,
                severity='medium' if action == 'create' else 'low',
                category='model_change',
                metadata={
                    'model': sender.__name__,
                    'action': action,
                    'fields_changed': list(changes.keys()) if changes else []
                }
            )
            
        except Exception as e:
            # Don't let audit logging break the application
            pass


@receiver(post_delete)
def log_model_delete(sender, instance, **kwargs):
    """Log model deletions."""
    if sender in TRACKED_MODELS:
        # Skip logging for AuditLog itself
        if sender == AuditLog:
            return
            
        try:
            # Get current user from thread local storage if available
            user = getattr(instance, '_audit_user', None)
            if not user:
                from threading import current_thread
                user = getattr(current_thread(), 'user', None)
            
            # Skip if no user context
            if not user or not hasattr(user, 'is_staff') or not user.is_staff:
                return
            
            content_type = ContentType.objects.get_for_model(sender)
            
            # Store the object data before deletion
            object_data = {}
            for field in sender._meta.fields:
                try:
                    value = getattr(instance, field.name)
                    # Convert to JSON serializable format
                    if hasattr(value, 'isoformat'):  # datetime objects
                        value = value.isoformat()
                    elif hasattr(value, '__dict__'):  # model instances
                        value = str(value)
                    object_data[field.name] = value
                except (AttributeError, ValueError):
                    object_data[field.name] = str(getattr(instance, field.name, None))
            
            # Create audit log entry
            AuditLog.objects.create(
                user=user,
                action='delete',
                description=f"Delete {sender.__name__}: {str(instance)}",
                content_type=content_type,
                object_id=str(instance.pk),
                object_repr=str(instance),
                model_name=sender.__name__,
                changes={'deleted_object': object_data},
                severity='high',
                category='model_change',
                metadata={
                    'model': sender.__name__,
                    'action': 'delete',
                    'deleted_data': object_data
                }
            )
            
        except Exception as e:
            # Don't let audit logging break the application
            pass


def set_audit_user(instance, user):
    """Helper function to set the audit user for an instance."""
    instance._audit_user = user
    return instance