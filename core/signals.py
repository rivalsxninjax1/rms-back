from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


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