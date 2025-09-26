from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta
from typing import Dict, Optional

from django.utils import timezone
from asgiref.sync import sync_to_async
from django.conf import settings

from .models import IntegrationToken, SyncLog


@dataclass
class AccessToken:
    token: str
    expires_at: Optional[timezone.datetime]


@dataclass
class TokenHealth:
    platform: str
    restaurant_id: str
    valid: bool
    expires_in_seconds: Optional[int]


class TokenError(Exception):
    pass


class OAuthManager:
    async def ensure_valid_token(self, platform: str, restaurant_id: str) -> AccessToken:
        """Guarantee valid token or raise specific exception.

        This implementation uses IntegrationToken and a naive refresh flow
        placeholder. Replace with provider-specific OAuth flows.
        """
        token = await sync_to_async(self._get_or_create_token)(platform, restaurant_id)
        if token.revoked:
            raise TokenError("token_revoked")
        if not token.access_token or token.is_expired():
            refreshed = await self._refresh_token(platform, token)
            if not refreshed:
                await sync_to_async(self._log)(platform, "token_refresh_failed", False, f"{restaurant_id}")
                raise TokenError("token_refresh_failed")
        return AccessToken(token=token.access_token, expires_at=token.expires_at)

    async def handle_token_refresh_failure(self, platform: str, error: TokenError) -> str:
        # Hook to notify admins, rotate credentials, or switch to backup account
        await sync_to_async(self._log)(platform, "token_refresh_failure", False, str(error))
        return "notified"

    async def bulk_token_health_check(self) -> Dict[str, TokenHealth]:
        results: Dict[str, TokenHealth] = {}
        tokens = await sync_to_async(list)(IntegrationToken.objects.all())
        for t in tokens:
            exp = None
            if t.expires_at:
                exp = int((t.expires_at - timezone.now()).total_seconds())
            key = f"{t.platform}:{t.restaurant_id}"
            results[key] = TokenHealth(
                platform=t.platform,
                restaurant_id=t.restaurant_id,
                valid=not t.revoked and bool(t.access_token and not t.is_expired()),
                expires_in_seconds=exp,
            )
        return results

    # ---------------------------- internals ----------------------------

    def _get_or_create_token(self, platform: str, restaurant_id: str) -> IntegrationToken:
        tok, _ = IntegrationToken.objects.get_or_create(platform=platform, restaurant_id=restaurant_id)
        return tok

    async def _refresh_token(self, platform: str, token: IntegrationToken) -> bool:
        # Placeholder: call provider refresh endpoints using refresh_token
        # For now, simulate refreshed token valid for 55 minutes
        new_token = f"{platform.lower()}_token_{int(timezone.now().timestamp())}"
        token.access_token = new_token
        token.expires_at = timezone.now() + timedelta(minutes=55)
        await sync_to_async(token.save)(update_fields=["access_token", "expires_at", "updated_at"])
        await sync_to_async(self._log)(platform, "token_refreshed", True, token.restaurant_id)
        return True

    def _log(self, provider: str, event: str, success: bool, message: str = ""):
        SyncLog.objects.create(provider=provider, event=event, success=success, message=message)

