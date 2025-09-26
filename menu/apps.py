from django.apps import AppConfig

class MenuConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "menu"

    def ready(self):
        # Import signals to propagate availability changes to middleware (if enabled)
        try:
            from . import signals  # noqa: F401
        except Exception:
            pass
