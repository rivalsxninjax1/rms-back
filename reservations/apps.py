from django.apps import AppConfig

class ReservationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "reservations"
    
    def ready(self):  # pragma: no cover - import-time wiring
        try:
            from . import signals  # noqa: F401
        except Exception:
            pass
