from django.conf import settings
from django.db import models
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.utils.html import strip_tags
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
import re
import uuid


class Table(models.Model):
    """
    Core Table model for centralized table management.
    This serves as the master table registry for the RMS system.
    """
    # Table number validation
    table_number_regex = RegexValidator(
        regex=r'^[A-Za-z0-9\-_]+$',
        message="Table number can only contain letters, numbers, hyphens, and underscores."
    )
    
    location = models.ForeignKey(
        "Location",
        on_delete=models.CASCADE,
        related_name="core_tables",
    )
    table_number = models.CharField(
        max_length=50,
        validators=[table_number_regex],
        help_text="Unique table identifier (alphanumeric, hyphens, underscores only)"
    )
    capacity = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(50)],
        help_text="Maximum seating capacity (1-50 people)"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this table is currently available for use"
    )
    table_type = models.CharField(
        max_length=20,
        choices=[
            ('dining', 'Dining Table'),
            ('bar', 'Bar Table'),
            ('outdoor', 'Outdoor Table'),
            ('private', 'Private Dining'),
        ],
        default='dining',
        help_text="Type of table for service categorization"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["location", "table_number"]
        ordering = ["location_id", "table_number"]
        indexes = [
            models.Index(fields=['location', 'is_active']),
            models.Index(fields=['table_type', 'is_active']),
        ]

    def clean(self):
        """Validate table data."""
        super().clean()
        
        # Sanitize table number
        if self.table_number:
            self.table_number = self.table_number.strip().upper()
            if not self.table_number:
                raise ValidationError({'table_number': 'Table number cannot be empty.'})
        
        # Validate capacity
        if self.capacity and (self.capacity < 1 or self.capacity > 50):
            raise ValidationError({'capacity': 'Table capacity must be between 1 and 50 people.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"Core-{self.location.name}#{self.table_number} ({self.capacity})"


class Organization(models.Model):
    # Phone number validation
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
    )
    
    name = models.CharField(
        max_length=200,
        help_text="Organization name (HTML tags will be stripped)"
    )
    tax_percent = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0.00,
        validators=[MinValueValidator(0.00), MaxValueValidator(100.00)],
        help_text="Tax percentage (0-100%)"
    )
    address = models.TextField(
        blank=True,
        help_text="Organization address (HTML tags will be stripped)"
    )
    phone = models.CharField(
        max_length=20, 
        blank=True,
        validators=[phone_regex],
        help_text="Contact phone number"
    )
    email = models.EmailField(
        blank=True,
        help_text="Contact email address"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['created_at']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(tax_percent__gte=0) & models.Q(tax_percent__lte=100),
                name='valid_tax_percent'
            ),
        ]

    def clean(self):
        """Validate and sanitize organization data."""
        super().clean()
        
        # Sanitize text fields
        if self.name:
            self.name = strip_tags(self.name).strip()
            if not self.name:
                raise ValidationError({'name': 'Organization name cannot be empty after sanitization.'})
            
            # Check for potentially malicious patterns
            if re.search(r'[<>"\'\\/]', self.name):
                raise ValidationError({'name': 'Organization name contains invalid characters.'})
        
        if self.address:
            self.address = strip_tags(self.address).strip()
            
        # Validate tax percentage
        if self.tax_percent < 0 or self.tax_percent > 100:
            raise ValidationError({'tax_percent': 'Tax percentage must be between 0 and 100.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class Location(models.Model):
    # Timezone validation
    timezone_regex = RegexValidator(
        regex=r'^[A-Za-z_]+/[A-Za-z_]+$|^UTC$',
        message="Timezone must be in format 'Region/City' or 'UTC'."
    )
    
    organization = models.ForeignKey(
        Organization, 
        on_delete=models.CASCADE, 
        related_name='locations'
    )
    name = models.CharField(
        max_length=200,
        help_text="Location name (HTML tags will be stripped)"
    )
    address = models.TextField(
        blank=True,
        help_text="Location address (HTML tags will be stripped)"
    )
    timezone = models.CharField(
        max_length=50, 
        default='UTC',
        validators=[timezone_regex],
        help_text="Timezone in format 'Region/City' or 'UTC'"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this location is currently active"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['organization', 'name']
        unique_together = [['organization', 'name']]
        indexes = [
            models.Index(fields=['organization', 'is_active']),
            models.Index(fields=['name']),
            models.Index(fields=['is_active']),
            models.Index(fields=['created_at']),
        ]

    def clean(self):
        """Validate and sanitize location data."""
        super().clean()
        
        # Sanitize text fields
        if self.name:
            self.name = strip_tags(self.name).strip()
            if not self.name:
                raise ValidationError({'name': 'Location name cannot be empty after sanitization.'})
            
            # Check for potentially malicious patterns
            if re.search(r'[<>"\'\\/]', self.name):
                raise ValidationError({'name': 'Location name contains invalid characters.'})
        
        if self.address:
            self.address = strip_tags(self.address).strip()
            
        # Validate timezone format
        if self.timezone and self.timezone != 'UTC':
            if not re.match(r'^[A-Za-z_]+/[A-Za-z_]+$', self.timezone):
                raise ValidationError({'timezone': 'Invalid timezone format. Use Region/City format or UTC.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.organization.name} - {self.name}"


class ServiceType(models.Model):
    """
    Service types available for orders and reservations.
    Centralizes service configuration and pricing.
    """
    
    name = models.CharField(
        max_length=50,
        unique=True,
        help_text="Service type name (e.g., 'Dine-in', 'Pickup', 'Delivery')"
    )
    
    code = models.CharField(
        max_length=20,
        unique=True,
        help_text="Service type code for API/system use"
    )
    
    description = models.TextField(
        blank=True,
        help_text="Service type description"
    )
    
    # Pricing configuration
    base_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
        help_text="Base service fee"
    )
    
    # Service configuration
    requires_table = models.BooleanField(
        default=False,
        help_text="Whether this service type requires table assignment"
    )
    
    allows_reservations = models.BooleanField(
        default=False,
        help_text="Whether reservations are allowed for this service type"
    )
    
    max_advance_days = models.PositiveIntegerField(
        default=30,
        validators=[MinValueValidator(1), MaxValueValidator(365)],
        help_text="Maximum days in advance for reservations (1-365)"
    )
    
    min_advance_minutes = models.PositiveIntegerField(
        default=30,
        validators=[MinValueValidator(0), MaxValueValidator(1440)],
        help_text="Minimum minutes in advance for reservations (0-1440)"
    )
    
    # Availability
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this service type is currently available"
    )
    
    # Display order
    sort_order = models.PositiveIntegerField(
        default=0,
        help_text="Display order (lower numbers appear first)"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['sort_order', 'name']
        indexes = [
            models.Index(fields=['is_active', 'sort_order']),
            models.Index(fields=['code']),
            models.Index(fields=['requires_table']),
            models.Index(fields=['allows_reservations']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(base_fee__gte=0),
                name="positive_service_base_fee"
            ),
            models.CheckConstraint(
                check=models.Q(max_advance_days__gte=1) & models.Q(max_advance_days__lte=365),
                name="valid_max_advance_days"
            ),
            models.CheckConstraint(
                check=models.Q(min_advance_minutes__gte=0) & models.Q(min_advance_minutes__lte=1440),
                name="valid_min_advance_minutes"
            ),
        ]
    
    def clean(self):
        """Validate service type data."""
        super().clean()
        
        # Strip HTML from text fields
        if self.name:
            self.name = strip_tags(self.name).strip()
        if self.code:
            self.code = strip_tags(self.code).strip().upper()
        if self.description:
            self.description = strip_tags(self.description)
        
        # Validate code format
        if self.code and not re.match(r'^[A-Z0-9_]+$', self.code):
            raise ValidationError({'code': 'Service code can only contain uppercase letters, numbers, and underscores.'})
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.name


class Reservation(models.Model):
    """
    Table reservations with atomic booking and conflict prevention.
    Supports both authenticated users and guest reservations.
    """
    
    # Reservation identification
    reservation_uuid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        help_text="Unique reservation identifier"
    )
    
    confirmation_number = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        help_text="Human-readable confirmation number"
    )
    
    # Customer information
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="core_reservations",
        help_text="Registered user (if applicable)"
    )
    
    guest_name = models.CharField(
        max_length=100,
        help_text="Guest name for reservation"
    )
    
    guest_phone = models.CharField(
        max_length=20,
        validators=[RegexValidator(
            regex=r'^\+?1?\d{9,15}$',
            message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
        )],
        help_text="Guest contact phone number"
    )
    
    guest_email = models.EmailField(
        blank=True,
        help_text="Guest email address (optional)"
    )
    
    # Reservation details
    table = models.ForeignKey(
        Table,
        on_delete=models.CASCADE,
        related_name="core_reservations",
        help_text="Reserved table"
    )
    
    service_type = models.ForeignKey(
        ServiceType,
        on_delete=models.CASCADE,
        related_name="core_reservations",
        help_text="Service type for this reservation"
    )
    
    party_size = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(50)],
        help_text="Number of guests (1-50)"
    )
    
    # Timing
    reservation_date = models.DateField(
        help_text="Date of reservation"
    )
    
    reservation_time = models.TimeField(
        help_text="Time of reservation"
    )
    
    duration_minutes = models.PositiveIntegerField(
        default=120,
        validators=[MinValueValidator(30), MaxValueValidator(480)],
        help_text="Expected duration in minutes (30-480)"
    )
    
    # Status tracking
    STATUS_PENDING = "pending"
    STATUS_CONFIRMED = "confirmed"
    STATUS_SEATED = "seated"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"
    STATUS_NO_SHOW = "no_show"
    
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending Confirmation"),
        (STATUS_CONFIRMED, "Confirmed"),
        (STATUS_SEATED, "Seated"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_CANCELLED, "Cancelled"),
        (STATUS_NO_SHOW, "No Show"),
    ]
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        help_text="Current reservation status"
    )
    
    # Status tracking
    confirmed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When reservation was confirmed"
    )
    
    seated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When party was seated"
    )
    
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When reservation was completed"
    )
    
    cancelled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When reservation was cancelled"
    )
    
    # Additional information
    special_requests = models.TextField(
        blank=True,
        help_text="Special requests or notes"
    )
    
    internal_notes = models.TextField(
        blank=True,
        help_text="Internal staff notes"
    )
    
    # Pricing (if applicable)
    deposit_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
        help_text="Required deposit amount"
    )
    
    deposit_paid = models.BooleanField(
        default=False,
        help_text="Whether deposit has been paid"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_core_reservations",
        help_text="Staff member who created the reservation"
    )
    
    class Meta:
        ordering = ['reservation_date', 'reservation_time']
        indexes = [
            models.Index(fields=['reservation_date', 'reservation_time']),
            models.Index(fields=['table', 'reservation_date', 'status']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['guest_phone']),
            models.Index(fields=['confirmation_number']),
            models.Index(fields=['reservation_uuid']),
            models.Index(fields=['status', 'reservation_date']),
            models.Index(fields=['service_type', 'status']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(party_size__gte=1) & models.Q(party_size__lte=50),
                name="valid_party_size"
            ),
            models.CheckConstraint(
                check=models.Q(duration_minutes__gte=30) & models.Q(duration_minutes__lte=480),
                name="valid_duration_minutes"
            ),
            models.CheckConstraint(
                check=models.Q(deposit_amount__gte=0),
                name="positive_deposit_amount"
            ),
        ]
    
    def clean(self):
        """Validate reservation data."""
        super().clean()
        
        # Strip HTML from text fields
        if self.guest_name:
            self.guest_name = strip_tags(self.guest_name).strip()
        if self.special_requests:
            self.special_requests = strip_tags(self.special_requests)
        if self.internal_notes:
            self.internal_notes = strip_tags(self.internal_notes)
        
        # Validate party size against table capacity
        if self.table and self.party_size > self.table.capacity:
            raise ValidationError({
                'party_size': f'Party size ({self.party_size}) exceeds table capacity ({self.table.capacity}).'
            })
        
        # Validate service type allows reservations
        if self.service_type and not self.service_type.allows_reservations:
            raise ValidationError({
                'service_type': f'Service type "{self.service_type.name}" does not allow reservations.'
            })
        
        # Validate service type requires table
        if self.service_type and self.service_type.requires_table and not self.table:
            raise ValidationError({
                'table': f'Service type "{self.service_type.name}" requires table assignment.'
            })
        
        # Validate reservation timing
        if self.reservation_date and self.reservation_time:
            reservation_datetime = timezone.datetime.combine(
                self.reservation_date, 
                self.reservation_time
            )
            reservation_datetime = timezone.make_aware(reservation_datetime)
            now = timezone.now()
            
            # Check minimum advance time
            if self.service_type:
                min_advance = timezone.timedelta(minutes=self.service_type.min_advance_minutes)
                if reservation_datetime < (now + min_advance):
                    raise ValidationError({
                        'reservation_time': f'Reservation must be at least {self.service_type.min_advance_minutes} minutes in advance.'
                    })
                
                # Check maximum advance time
                max_advance = timezone.timedelta(days=self.service_type.max_advance_days)
                if reservation_datetime > (now + max_advance):
                    raise ValidationError({
                        'reservation_date': f'Reservation cannot be more than {self.service_type.max_advance_days} days in advance.'
                    })
    
    def save(self, *args, **kwargs):
        # Generate confirmation number if not set
        if not self.confirmation_number:
            self.confirmation_number = self.generate_confirmation_number()
        
        self.full_clean()
        super().save(*args, **kwargs)
    
    @classmethod
    def generate_confirmation_number(cls):
        """Generate a unique confirmation number."""
        import random
        import string
        
        while True:
            # Generate 8-character alphanumeric code
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            if not cls.objects.filter(confirmation_number=code).exists():
                return code
    
    @transaction.atomic
    def check_availability(self):
        """Check if table is available for the requested time slot."""
        if not self.table or not self.reservation_date or not self.reservation_time:
            return False
        
        # Calculate time range
        start_datetime = timezone.datetime.combine(
            self.reservation_date, 
            self.reservation_time
        )
        start_datetime = timezone.make_aware(start_datetime)
        end_datetime = start_datetime + timezone.timedelta(minutes=self.duration_minutes)
        
        # Check for conflicting reservations
        conflicting_reservations = Reservation.objects.select_for_update().filter(
            table=self.table,
            reservation_date=self.reservation_date,
            status__in=[self.STATUS_CONFIRMED, self.STATUS_SEATED]
        ).exclude(pk=self.pk if self.pk else None)
        
        for reservation in conflicting_reservations:
            existing_start = timezone.datetime.combine(
                reservation.reservation_date,
                reservation.reservation_time
            )
            existing_start = timezone.make_aware(existing_start)
            existing_end = existing_start + timezone.timedelta(minutes=reservation.duration_minutes)
            
            # Check for overlap
            if (start_datetime < existing_end and end_datetime > existing_start):
                return False
        
        return True
    
    @transaction.atomic
    def confirm_reservation(self, confirmed_by=None):
        """Atomically confirm reservation with availability check."""
        # Lock reservation for update
        reservation = Reservation.objects.select_for_update().get(pk=self.pk)
        
        if reservation.status != self.STATUS_PENDING:
            raise ValidationError(f"Cannot confirm reservation with status '{reservation.status}'.")
        
        # Check availability
        if not reservation.check_availability():
            raise ValidationError("Table is not available for the requested time slot.")
        
        # Confirm reservation
        reservation.status = self.STATUS_CONFIRMED
        reservation.confirmed_at = timezone.now()
        if confirmed_by:
            reservation.created_by = confirmed_by
        
        reservation.save(update_fields=['status', 'confirmed_at', 'created_by', 'updated_at'])
        return reservation
    
    @transaction.atomic
    def cancel_reservation(self, cancelled_by=None):
        """Cancel reservation."""
        if self.status in [self.STATUS_CANCELLED, self.STATUS_COMPLETED, self.STATUS_NO_SHOW]:
            raise ValidationError(f"Cannot cancel reservation with status '{self.status}'.")
        
        self.status = self.STATUS_CANCELLED
        self.cancelled_at = timezone.now()
        if cancelled_by:
            self.created_by = cancelled_by
        
        self.save(update_fields=['status', 'cancelled_at', 'created_by', 'updated_at'])
    
    def get_end_time(self):
        """Get reservation end time."""
        if not self.reservation_time:
            return None
        
        start_datetime = timezone.datetime.combine(
            timezone.datetime.today(),
            self.reservation_time
        )
        end_datetime = start_datetime + timezone.timedelta(minutes=self.duration_minutes)
        return end_datetime.time()
    
    def __str__(self):
        return f"Reservation {self.confirmation_number} - {self.guest_name} ({self.party_size} guests)"
