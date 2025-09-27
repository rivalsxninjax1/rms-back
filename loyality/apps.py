from __future__ import annotations

from django.apps import AppConfig


class LoyalityConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "loyality"
    verbose_name = "Loyalty & Ranks"

    def ready(self) -> None:  # pragma: no cover - startup wiring
        # Connect signal handlers (create LoyaltyProfile on user creation, etc.)
        try:
            from . import signals  # noqa: F401
        except Exception:
            # If migrations not applied yet or during collectstatic, be permissive.
            pass
