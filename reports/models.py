from __future__ import annotations

from django.db import models
from django.core.validators import MinValueValidator
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from decimal import Decimal
import json

User = get_user_model()


class DailySales(models.Model):
    """
    Minimal Daily Sales aggregate so `reports.views` can import and the
    admin/API can read something stable. Amounts are stored in integer cents.
    """
    date = models.DateField(unique=True)
    total_orders = models.PositiveIntegerField(default=0)

    subtotal_cents = models.PositiveIntegerField(default=0)
    tip_cents = models.PositiveIntegerField(default=0)
    discount_cents = models.PositiveIntegerField(default=0)
    total_cents = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self) -> str:  # pragma: no cover
        return f"DailySales {self.date} (orders={self.total_orders})"


class ShiftReport(models.Model):
    """
    Minimal shift report record (non-blocking). Keeps the interface that other
    parts of the code expect: a per-shift roll-up with integer-cents totals.
    """
    SHIFT_CHOICES = [
        ("morning", "Morning"),
        ("afternoon", "Afternoon"),
        ("evening", "Evening"),
        ("night", "Night"),
    ]

    date = models.DateField()
    shift = models.CharField(max_length=16, choices=SHIFT_CHOICES, default="evening")
    staff = models.CharField(max_length=120, blank=True, help_text="Shift lead or cashier")

    orders_count = models.PositiveIntegerField(default=0)
    total_cents = models.PositiveIntegerField(default=0)

    # Cash drawer tracking
    opened_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    cash_open_cents = models.IntegerField(default=0, help_text="Starting cash in drawer (¢)")
    cash_close_cents = models.IntegerField(default=0, help_text="Ending cash in drawer (¢)")
    cash_sales_cents = models.IntegerField(default=0, help_text="Cash sales total (¢) recorded by POS")
    over_short_cents = models.IntegerField(default=0, help_text="Cash over/short (¢) = close - open - cash_sales")
    notes = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("date", "shift")]
        ordering = ["-date", "shift", "-id"]

    def __str__(self) -> str:  # pragma: no cover
        return f"ShiftReport {self.date} {self.shift} (orders={self.orders_count})"


class AuditLog(models.Model):
    """
    Comprehensive audit logging for admin actions and system changes.
    Tracks who did what, when, and what changed.
    """
    
    ACTION_CHOICES = [
        ('CREATE', 'Create'),
        ('UPDATE', 'Update'),
        ('DELETE', 'Delete'),
        ('LOGIN', 'Login'),
        ('LOGOUT', 'Logout'),
        ('VIEW', 'View'),
        ('EXPORT', 'Export'),
        ('IMPORT', 'Import'),
        ('SYSTEM', 'System Action'),
    ]
    
    SEVERITY_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('CRITICAL', 'Critical'),
    ]
    
    # Who performed the action
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="User who performed the action"
    )
    
    # What action was performed
    action = models.CharField(
        max_length=20,
        choices=ACTION_CHOICES,
        help_text="Type of action performed"
    )
    
    # What object was affected (generic foreign key)
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Action details
    description = models.TextField(
        help_text="Human-readable description of the action"
    )
    
    # Technical details
    model_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Name of the affected model"
    )
    
    object_repr = models.CharField(
        max_length=200,
        blank=True,
        help_text="String representation of the affected object"
    )
    
    # Change tracking
    changes = models.JSONField(
        default=dict,
        blank=True,
        help_text="JSON representation of field changes"
    )
    
    # Request context
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address of the user"
    )
    
    user_agent = models.TextField(
        blank=True,
        help_text="User agent string from the request"
    )
    
    request_path = models.CharField(
        max_length=500,
        blank=True,
        help_text="Request path/URL"
    )
    
    request_method = models.CharField(
        max_length=10,
        blank=True,
        help_text="HTTP method (GET, POST, etc.)"
    )
    
    # Severity and categorization
    severity = models.CharField(
        max_length=10,
        choices=SEVERITY_CHOICES,
        default='LOW',
        help_text="Severity level of the action"
    )
    
    category = models.CharField(
        max_length=50,
        blank=True,
        help_text="Category for grouping similar actions"
    )
    
    # Additional metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata about the action"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['action', '-created_at']),
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['severity', '-created_at']),
            models.Index(fields=['category', '-created_at']),
            models.Index(fields=['ip_address', '-created_at']),
        ]
    
    def __str__(self) -> str:
        user_str = self.user.username if self.user else 'Anonymous'
        return f"{user_str} {self.action} {self.model_name} at {self.created_at}"
    
    @classmethod
    def log_action(cls, user, action, description, content_object=None, 
                   changes=None, request=None, severity='LOW', category=''):
        """
        Convenience method to create audit log entries.
        """
        audit_data = {
            'user': user,
            'action': action,
            'description': description,
            'severity': severity,
            'category': category,
        }
        
        if content_object:
            audit_data.update({
                'content_object': content_object,
                'model_name': content_object._meta.model_name,
                'object_repr': str(content_object),
            })
        
        if changes:
            audit_data['changes'] = changes
        
        if request:
            audit_data.update({
                'ip_address': cls._get_client_ip(request),
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'request_path': request.path,
                'request_method': request.method,
            })
        
        return cls.objects.create(**audit_data)
    
    @staticmethod
    def _get_client_ip(request):
        """Extract client IP from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
