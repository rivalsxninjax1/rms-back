from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
    
    def ready(self):
        """Register table synchronization signals when the app is ready."""
        from .signals import register_table_sync_signals
        register_table_sync_signals()
