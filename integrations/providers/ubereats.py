from __future__ import annotations

import hmac
import hashlib
from typing import Any, Dict, List, Optional
from django.conf import settings
from .base import BaseClient, APIResponse, backoff


class UberEatsClient(BaseClient):
    def __init__(self):
        env = (getattr(settings, "UBEREATS_ENVIRONMENT", "sandbox") or "sandbox").lower()
        base = "https://api.uber.com" if env == "production" else "https://sandbox-api.uber.com"
        headers = {
            "Authorization": f"Bearer {getattr(settings, 'UBEREATS_ACCESS_TOKEN', '')}",
            "Content-Type": "application/json",
        }
        super().__init__(base_url=base, headers=headers, rpm=120)

    @backoff()
    def list_orders(self, since_iso: Optional[str] = None) -> APIResponse:
        params = {}
        if since_iso:
            params["since"] = since_iso
        return self._request("GET", "/v1/eats/orders", params=params)

    @backoff()
    def get_order(self, external_id: str) -> APIResponse:
        return self._request("GET", f"/v1/eats/orders/{external_id}")

    @backoff()
    def update_order_status(self, external_id: str, status: str) -> APIResponse:
        body = {"status": status}
        return self._request("POST", f"/v1/eats/orders/{external_id}/status", json=body)

    @backoff()
    def push_menu(self, payload: Dict[str, Any]) -> APIResponse:
        return self._request("PUT", f"/v1/eats/menu", json=payload)

    @staticmethod
    def verify_webhook(signature: str, raw_body: bytes) -> bool:
        secret = getattr(settings, "UBEREATS_WEBHOOK_SECRET", "") or ""
        try:
            sig = signature or ""
            if sig.startswith("sha256="):
                sig = sig.split("=", 1)[1]
            digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
            return hmac.compare_digest(sig, digest)
        except Exception:
            return False

