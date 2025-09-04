from django.apps import AppConfig
from django.conf import settings
from django.db.models.signals import post_migrate


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
    
    def ready(self):
        """Register table synchronization signals when the app is ready."""
        from .signals import register_table_sync_signals
        register_table_sync_signals()

        # Wire additional receivers (order_paid, order_status_changed)
        try:
            from . import receivers  # noqa: F401
        except Exception:
            # Keep startup resilient if optional deps missing
            pass

        # Optionally auto-seed tables after migrations in dev environments
        def _post_migrate_seed(sender, **kwargs):
            try:
                auto = getattr(settings, "AUTO_SEED_TABLES", None)
                if auto is None:
                    auto = getattr(settings, "DEBUG", False)
                if not auto:
                    return
                from core.models import Table
                if not Table.objects.exists():
                    from .seed import seed_default_tables
                    seed_default_tables(min_tables=6)
            except Exception:
                # Ignore seeding failures silently
                pass

        post_migrate.connect(_post_migrate_seed, sender=self)
