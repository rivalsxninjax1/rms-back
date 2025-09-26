from __future__ import annotations

import asyncio
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional

from django.core.cache import cache


@dataclass
class Address:
    street: str
    city: str
    postal_code: str
    lat: Optional[float] = None
    lng: Optional[float] = None


@dataclass
class Option:
    platform: str
    fee: Decimal
    eta_minutes: int
    available: bool
    promotion: Optional[str] = None


@dataclass
class DeliveryOptions:
    options: List[Option]


@dataclass
class FallbackOptions:
    options: List[Option]
    reason: str


@dataclass
class RecommendedOption:
    platform: str
    rationale: str


class DeliveryOptionsEngine:
    async def get_unified_options(self, address: Address, order_value: Decimal) -> DeliveryOptions:
        """Return real-time delivery options from all available platforms.

        Uses short-lived cache to avoid rate limiting.
        """
        cache_key = f"opts:{address.postal_code}:{int(order_value)}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        # Placeholder: call platform quote APIs concurrently
        opts = DeliveryOptions(options=[
            Option(platform="UBEREATS", fee=Decimal("3.99"), eta_minutes=35, available=True),
            Option(platform="DOORDASH", fee=Decimal("4.49"), eta_minutes=30, available=True),
            Option(platform="GRUBHUB", fee=Decimal("4.99"), eta_minutes=45, available=True),
        ])
        cache.set(cache_key, opts, timeout=30)
        return opts

    async def handle_platform_outage(self, failed_platforms: List[str]) -> FallbackOptions:
        """Provide graceful degradation when platforms are down."""
        # Use last-known-good from cache and mark as estimated
        est = [
            Option(platform=p, fee=Decimal("4.99"), eta_minutes=40, available=False, promotion="estimate")
            for p in failed_platforms
        ]
        return FallbackOptions(options=est, reason="platform_outage")

    async def optimize_platform_selection(self, customer: Dict, options: DeliveryOptions) -> RecommendedOption:
        """AI-driven platform recommendation engine.

        Placeholder heuristic: prefer lowest fee, tie-break by ETA.
        """
        best = sorted(options.options, key=lambda o: (o.fee, o.eta_minutes))[0]
        return RecommendedOption(platform=best.platform, rationale="lowest_fee_then_fastest")

