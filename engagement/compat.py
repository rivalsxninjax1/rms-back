"""
Compatibility shims for the engagement app.

This exposes LoyaltyTier for legacy imports by redirecting to the new
tip-based loyalty model living in the `loyality` app.

Any code that previously did:
    from engagement.models import LoyaltyTier
should instead import:
    from engagement.compat import LoyaltyTier
"""

try:
    # Re-export the TipLoyaltySetting class under the expected name LoyaltyTier.
    # This keeps admin and any other logic happy without adding new DB tables here.
    from loyality.models import TipLoyaltySetting as LoyaltyTier  # noqa: F401
except Exception:
    # If loyality isn't installed yet, define a stub so admin import doesn't crash.
    class LoyaltyTier:  # type: ignore
        pass
