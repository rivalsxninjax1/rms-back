from __future__ import annotations

from django.conf import settings
from django.db import models
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.core.validators import RegexValidator
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import timedelta
import uuid


class User(AbstractUser):
    """
    Enhanced custom user model with security features and profile management.
    
    We explicitly redeclare 'groups' and 'user_permissions' with explicit 'through='
    models (User_groups, User_user_permissions) so Django knows the FK targets and
    avoids the admin/system-check errors you were seeing.
    """
    
    # Phone number validation
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
    )
    
    # Additional profile fields
    phone_number = models.CharField(
        validators=[phone_regex], 
        max_length=17, 
        blank=True, 
        null=True,
        help_text="Phone number for account verification and notifications"
    )
    
    # Security fields
    is_email_verified = models.BooleanField(
        default=False,
        help_text="Whether the user's email address has been verified"
    )
    
    is_phone_verified = models.BooleanField(
        default=False,
        help_text="Whether the user's phone number has been verified"
    )
    
    failed_login_attempts = models.PositiveIntegerField(
        default=0,
        help_text="Number of consecutive failed login attempts"
    )
    
    account_locked_until = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Account is locked until this timestamp"
    )
    
    password_changed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the password was last changed"
    )
    
    # Profile fields
    date_of_birth = models.DateField(
        null=True, 
        blank=True,
        help_text="User's date of birth for age verification"
    )
    
    profile_picture = models.ImageField(
        upload_to='profile_pictures/',
        null=True,
        blank=True,
        help_text="User's profile picture"
    )
    
    # Privacy settings
    allow_marketing_emails = models.BooleanField(
        default=False,
        help_text="Whether user consents to marketing emails"
    )
    
    # Tracking fields
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    last_activity = models.DateTimeField(null=True, blank=True)
    
    # Re-declare M2M to use explicit through models that we define below.
    groups = models.ManyToManyField(
        Group,
        verbose_name="groups",
        blank=True,
        help_text="The groups this user belongs to.",
        related_name="user_set",
        related_query_name="user",
        through="accounts.User_groups",
    )

    user_permissions = models.ManyToManyField(
        Permission,
        verbose_name="user permissions",
        blank=True,
        help_text="Specific permissions for this user.",
        related_name="user_set",
        related_query_name="user",
        through="accounts.User_user_permissions",
    )

    class Meta:
        swappable = "AUTH_USER_MODEL"
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['phone_number']),
            models.Index(fields=['is_active', 'is_email_verified']),
            models.Index(fields=['last_activity']),
        ]
    
    def clean(self):
        super().clean()
        if self.email:
            self.email = self.email.lower()
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
    
    def __str__(self) -> str:
        return self.get_username() or f"User#{self.pk}"
    
    @property
    def is_account_locked(self):
        """Check if account is currently locked."""
        if self.account_locked_until:
            return timezone.now() < self.account_locked_until
        return False
    
    def lock_account(self, duration_minutes=30):
        """Lock account for specified duration."""
        self.account_locked_until = timezone.now() + timedelta(minutes=duration_minutes)
        self.save(update_fields=['account_locked_until'])
    
    def unlock_account(self):
        """Unlock account and reset failed attempts."""
        self.account_locked_until = None
        self.failed_login_attempts = 0
        self.save(update_fields=['account_locked_until', 'failed_login_attempts'])
    
    def increment_failed_login(self):
        """Increment failed login attempts and lock if threshold reached."""
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= 5:
            self.lock_account()
        self.save(update_fields=['failed_login_attempts'])
    
    def reset_failed_login(self):
        """Reset failed login attempts on successful login."""
        if self.failed_login_attempts > 0:
            self.failed_login_attempts = 0
            self.save(update_fields=['failed_login_attempts'])
    
    def update_last_activity(self):
        """Update last activity timestamp."""
        self.last_activity = timezone.now()
        self.save(update_fields=['last_activity'])
    
    def password_needs_change(self, max_age_days=90):
        """Check if password needs to be changed based on age."""
        if not self.password_changed_at:
            return True
        age = timezone.now() - self.password_changed_at
        return age.days > max_age_days
    
    def get_full_name(self):
        """Return the first_name plus the last_name, with a space in between."""
        full_name = f"{self.first_name} {self.last_name}".strip()
        return full_name or self.get_username()
    
    def get_short_name(self):
        """Return the short name for the user."""
        return self.first_name or self.get_username()


class User_groups(models.Model):
    """
    Explicit 'through' table linking accounts.User <-> auth.Group.
    Fixes: accounts.User_groups.user: (fields.E301) when using a swapped user model
    """
    # ---- MINIMAL FIX: point FK to the swapped user model ----
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    group = models.ForeignKey(Group, on_delete=models.CASCADE)

    class Meta:
        db_table = "accounts_user_groups"
        unique_together = (("user", "group"),)

    def __str__(self) -> str:
        return f"{self.user_id} ↔ {self.group_id}"


class User_user_permissions(models.Model):
    """
    Explicit 'through' table linking accounts.User <-> auth.Permission.
    Fixes: accounts.User_user_permissions.user: (fields.E301) when using a swapped user model
    """
    # ---- MINIMAL FIX: point FK to the swapped user model ----
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE)

    class Meta:
        db_table = "accounts_user_user_permissions"
        unique_together = (("user", "permission"),)

    def __str__(self) -> str:
        return f"{self.user_id} ↔ {self.permission_id}"
