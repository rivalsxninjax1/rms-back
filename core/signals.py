from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
import logging
import json
from threading import local

logger = logging.getLogger(__name__)

# Thread-local storage to track original values for audit logging
_thread_locals = local()


def sync_table_to_other_apps(sender, instance, created, **kwargs):
    """
    Sync table changes to other apps when a table is created or updated.
    """
    # Import models dynamically to avoid circular imports
    try:
        from reservations.models import Table as ReservationTable
    except ImportError:
        ReservationTable = None
        
    try:
        from core.models import Table as CoreTable
    except ImportError:
        CoreTable = None
        
    try:
        from inventory.models import Table as InventoryTable
    except ImportError:
        InventoryTable = None

    # Determine source app
    source_app = None
    if sender == ReservationTable:
        source_app = 'reservations'
    elif sender == CoreTable:
        source_app = 'core'
    elif sender == InventoryTable:
        source_app = 'inventory'
    else:
        return  # Unknown sender

    # Get target models
    target_models = []
    if source_app != 'reservations' and ReservationTable:
        target_models.append(('reservations', ReservationTable))
    if source_app != 'core' and CoreTable:
        target_models.append(('core', CoreTable))
    if source_app != 'inventory' and InventoryTable:
        target_models.append(('inventory', InventoryTable))

    # Sync to each target model
    for target_name, target_model in target_models:
        try:
            existing = target_model.objects.filter(
                location=instance.location,
                table_number=instance.table_number
            ).first()

            if existing:
                # Update existing table
                updated = False
                if existing.capacity != instance.capacity:
                    existing.capacity = instance.capacity
                    updated = True
                if existing.is_active != instance.is_active:
                    existing.is_active = instance.is_active
                    updated = True
                    
                if updated:
                    existing.save()
                    logger.info(f'Synced table {instance.table_number} update to {target_name}')
            elif created:
                # Create new table only if the source table was just created
                table_data = {
                    'location': instance.location,
                    'table_number': instance.table_number,
                    'capacity': instance.capacity,
                    'is_active': instance.is_active,
                }
                
                # Add model-specific fields with defaults
                if target_name == 'core':
                    table_data['table_type'] = getattr(instance, 'table_type', 'dining')
                elif target_name == 'inventory':
                    table_data.update({
                        'condition': getattr(instance, 'condition', 'good'),
                        'purchase_date': getattr(instance, 'purchase_date', timezone.now().date()),
                        'purchase_cost': getattr(instance, 'purchase_cost', 0.00),
                    })
                
                target_model.objects.create(**table_data)
                logger.info(f'Synced new table {instance.table_number} to {target_name}')
                
        except Exception as e:
            logger.error(f'Failed to sync table {instance.table_number} to {target_name}: {e}')


def sync_table_deletion(sender, instance, **kwargs):
    """
    Sync table deletions to other apps (mark as inactive instead of deleting).
    """
    # Import models dynamically
    try:
        from reservations.models import Table as ReservationTable
    except ImportError:
        ReservationTable = None
        
    try:
        from core.models import Table as CoreTable
    except ImportError:
        CoreTable = None
        
    try:
        from inventory.models import Table as InventoryTable
    except ImportError:
        InventoryTable = None

    # Determine source app
    source_app = None
    if sender == ReservationTable:
        source_app = 'reservations'
    elif sender == CoreTable:
        source_app = 'core'
    elif sender == InventoryTable:
        source_app = 'inventory'
    else:
        return

    # Get target models
    target_models = []
    if source_app != 'reservations' and ReservationTable:
        target_models.append(('reservations', ReservationTable))
    if source_app != 'core' and CoreTable:
        target_models.append(('core', CoreTable))
    if source_app != 'inventory' and InventoryTable:
        target_models.append(('inventory', InventoryTable))

    # Mark as inactive in target models instead of deleting
    for target_name, target_model in target_models:
        try:
            target_model.objects.filter(
                location=instance.location,
                table_number=instance.table_number
            ).update(is_active=False)
            logger.info(f'Marked table {instance.table_number} as inactive in {target_name}')
        except Exception as e:
            logger.error(f'Failed to sync table deletion to {target_name}: {e}')


# Connect signals - these will be registered when the app is ready
def register_table_sync_signals():
    """
    Register table synchronization signals for all table models.
    """
    try:
        from reservations.models import Table as ReservationTable
        post_save.connect(sync_table_to_other_apps, sender=ReservationTable)
        post_delete.connect(sync_table_deletion, sender=ReservationTable)
    except ImportError:
        pass
        
    try:
        from core.models import Table as CoreTable
        post_save.connect(sync_table_to_other_apps, sender=CoreTable)
        post_delete.connect(sync_table_deletion, sender=CoreTable)
    except ImportError:
        pass
        
    try:
        from inventory.models import Table as InventoryTable
        post_save.connect(sync_table_to_other_apps, sender=InventoryTable)
        post_delete.connect(sync_table_deletion, sender=InventoryTable)
    except ImportError:
        pass


# Audit logging functions
def get_model_fields_dict(instance):
    """
    Get a dictionary of all field values for a model instance.
    """
    fields_dict = {}
    for field in instance._meta.fields:
        field_name = field.name
        field_value = getattr(instance, field_name)
        
        # Convert non-serializable values to strings
        if hasattr(field_value, 'isoformat'):  # datetime objects
            field_value = field_value.isoformat()
        elif hasattr(field_value, '__str__') and not isinstance(field_value, (str, int, float, bool, type(None))):
            field_value = str(field_value)
            
        fields_dict[field_name] = field_value
    return fields_dict


def get_current_user():
    """
    Get the current user from thread-local storage.
    """
    return getattr(_thread_locals, 'user', None)


def set_current_user(user):
    """
    Set the current user in thread-local storage.
    """
    _thread_locals.user = user


def create_audit_log(model_name, object_id, action, diff_data, user=None):
    """
    Create an audit log entry.
    """
    try:
        from core.models import AuditLog
        AuditLog.objects.create(
            model_name=model_name,
            object_id=str(object_id),
            action=action,
            by_user=user or get_current_user(),
            diff=diff_data
        )
    except Exception as e:
        logger.error(f'Failed to create audit log: {e}')


@receiver(post_save)
def audit_model_save(sender, instance, created, **kwargs):
    """
    Audit save operations for tracked models.
    """
    # Only audit specific models
    tracked_models = ['Order', 'Reservation', 'Payment']
    model_name = sender.__name__
    
    if model_name not in tracked_models:
        return
        
    try:
        if created:
            # For new objects, log all fields
            diff_data = {
                'action': 'create',
                'new_values': get_model_fields_dict(instance)
            }
            create_audit_log(model_name, instance.pk, 'create', diff_data)
        else:
            # For updates, we need to compare with original values
            # This requires storing original values before save (in a pre_save signal)
            original_key = f'{model_name}_{instance.pk}_original'
            original_values = getattr(_thread_locals, original_key, None)
            
            if original_values:
                current_values = get_model_fields_dict(instance)
                changes = {}
                
                for field_name, new_value in current_values.items():
                    old_value = original_values.get(field_name)
                    if old_value != new_value:
                        changes[field_name] = {
                            'old': old_value,
                            'new': new_value
                        }
                
                if changes:
                    diff_data = {
                        'action': 'update',
                        'changes': changes
                    }
                    create_audit_log(model_name, instance.pk, 'update', diff_data)
                
                # Clean up thread-local storage
                delattr(_thread_locals, original_key)
                
    except Exception as e:
        logger.error(f'Failed to audit save for {model_name}: {e}')


@receiver(post_delete)
def audit_model_delete(sender, instance, **kwargs):
    """
    Audit delete operations for tracked models.
    """
    # Only audit specific models
    tracked_models = ['Order', 'Reservation', 'Payment']
    model_name = sender.__name__
    
    if model_name not in tracked_models:
        return
        
    try:
        diff_data = {
            'action': 'delete',
            'deleted_values': get_model_fields_dict(instance)
        }
        create_audit_log(model_name, instance.pk, 'delete', diff_data)
    except Exception as e:
        logger.error(f'Failed to audit delete for {model_name}: {e}')


# Pre-save signal to capture original values
from django.db.models.signals import pre_save

@receiver(pre_save)
def capture_original_values(sender, instance, **kwargs):
    """
    Capture original values before save for audit comparison.
    """
    tracked_models = ['Order', 'Reservation', 'Payment']
    model_name = sender.__name__
    
    if model_name not in tracked_models or not instance.pk:
        return
        
    try:
        # Get the original instance from database
        original_instance = sender.objects.get(pk=instance.pk)
        original_values = get_model_fields_dict(original_instance)
        
        # Store in thread-local storage
        original_key = f'{model_name}_{instance.pk}_original'
        setattr(_thread_locals, original_key, original_values)
    except sender.DoesNotExist:
        # Object doesn't exist yet (shouldn't happen in pre_save, but just in case)
        pass
    except Exception as e:
        logger.error(f'Failed to capture original values for {model_name}: {e}')