from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from core.models import Location


class Command(BaseCommand):
    help = 'Synchronize tables across all three apps (reservations, core, inventory)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--source',
            type=str,
            choices=['reservations', 'core', 'inventory'],
            help='Source app to sync from (default: auto-detect)'
        )
        parser.add_argument(
            '--target',
            type=str,
            choices=['reservations', 'core', 'inventory'],
            help='Target app to sync to (default: all others)'
        )
        parser.add_argument(
            '--location',
            type=int,
            help='Sync tables for specific location ID only'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be synced without making changes'
        )

    def handle(self, *args, **options):
        # Import models dynamically to avoid import errors
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

        models = {
            'reservations': ReservationTable,
            'core': CoreTable,
            'inventory': InventoryTable
        }
        
        available_models = {k: v for k, v in models.items() if v is not None}
        
        if len(available_models) < 2:
            self.stdout.write(
                self.style.ERROR('At least 2 table models must be available for synchronization')
            )
            return

        source = options.get('source')
        target = options.get('target')
        location_id = options.get('location')
        dry_run = options.get('dry_run')

        # Auto-detect source if not specified (use the one with most tables)
        if not source:
            table_counts = {}
            for app_name, model in available_models.items():
                count = model.objects.filter(is_active=True).count()
                table_counts[app_name] = count
            source = max(table_counts, key=table_counts.get)
            self.stdout.write(f'Auto-detected source: {source} ({table_counts[source]} tables)')

        source_model = available_models.get(source)
        if not source_model:
            self.stdout.write(
                self.style.ERROR(f'Source model "{source}" not available')
            )
            return

        # Get source tables
        source_tables = source_model.objects.filter(is_active=True)
        if location_id:
            source_tables = source_tables.filter(location_id=location_id)
        source_tables = source_tables.select_related('location')

        self.stdout.write(f'Found {source_tables.count()} tables in {source} app')

        # Determine target models
        if target:
            target_models = {target: available_models.get(target)}
        else:
            target_models = {k: v for k, v in available_models.items() if k != source}

        sync_stats = {'created': 0, 'updated': 0, 'skipped': 0}

        with transaction.atomic():
            for table in source_tables:
                for target_name, target_model in target_models.items():
                    if not target_model:
                        continue
                        
                    # Check if table already exists in target
                    existing = target_model.objects.filter(
                        location=table.location,
                        table_number=table.table_number
                    ).first()

                    if existing:
                        # Update existing table
                        updated = False
                        if existing.capacity != table.capacity:
                            existing.capacity = table.capacity
                            updated = True
                        if existing.is_active != table.is_active:
                            existing.is_active = table.is_active
                            updated = True
                            
                        if updated:
                            if not dry_run:
                                existing.save()
                            sync_stats['updated'] += 1
                            self.stdout.write(
                                f'Updated table {table.table_number} in {target_name}'
                            )
                        else:
                            sync_stats['skipped'] += 1
                    else:
                        # Create new table
                        table_data = {
                            'location': table.location,
                            'table_number': table.table_number,
                            'capacity': table.capacity,
                            'is_active': table.is_active,
                        }
                        
                        # Add model-specific fields
                        if target_name == 'core' and hasattr(table, 'table_type'):
                            table_data['table_type'] = getattr(table, 'table_type', 'dining')
                        elif target_name == 'inventory':
                            table_data.update({
                                'condition': getattr(table, 'condition', 'good'),
                                'purchase_date': getattr(table, 'purchase_date', timezone.now().date()),
                                'purchase_cost': getattr(table, 'purchase_cost', 0.00),
                            })
                        
                        if not dry_run:
                            target_model.objects.create(**table_data)
                        sync_stats['created'] += 1
                        self.stdout.write(
                            f'Created table {table.table_number} in {target_name}'
                        )

            if dry_run:
                self.stdout.write(
                    self.style.WARNING('DRY RUN - No changes were made')
                )
            
        self.stdout.write(
            self.style.SUCCESS(
                f'Sync completed: {sync_stats["created"]} created, '
                f'{sync_stats["updated"]} updated, {sync_stats["skipped"]} skipped'
            )
        )