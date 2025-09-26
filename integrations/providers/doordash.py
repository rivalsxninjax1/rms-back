from __future__ import annotations

import hmac
import hashlib
from typing import Any, Dict, Optional
from django.conf import settings
from .base import BaseClient, APIResponse, backoff


class DoorDashClient(BaseClient):
    def __init__(self):
        env = (getattr(settings, "DOORDASH_ENVIRONMENT", "sandbox") or "sandbox").lower()
        base = "https://openapi.doordash.com" if env == "production" else "https://openapi-sandbox.doordash.com"
        headers = {
            # Depending on auth flow; placeholder assumes key/secret HMAC or OAuth
            "X-Developer-Id": getattr(settings, "DOORDASH_DEVELOPER_ID", ""),
            "X-Key-Id": getattr(settings, "DOORDASH_KEY_ID", ""),
            "Content-Type": "application/json",
        }
        super().__init__(base_url=base, headers=headers, rpm=120)

    @backoff()
    def list_orders(self, since_iso: Optional[str] = None) -> APIResponse:
        params = {}
        if since_iso:
            params["since"] = since_iso
        return self._request("GET", "/v1/merchant/orders", params=params)

    @backoff()
    def get_order(self, external_id: str) -> APIResponse:
        return self._request("GET", f"/v1/merchant/orders/{external_id}")

    @backoff()
    def update_order_status(self, external_id: str, status: str) -> APIResponse:
        body = {"status": status}
        return self._request("POST", f"/v1/merchant/orders/{external_id}/status", json=body)

    @backoff()
    def push_menu(self, payload: Dict[str, Any]) -> APIResponse:
        return self._request("PUT", f"/v1/merchant/menu", json=payload)

    @staticmethod
    def verify_webhook(signature: str, raw_body: bytes) -> bool:
        secret = getattr(settings, "DOORDASH_WEBHOOK_SECRET", "") or ""
        try:
            sig = signature or ""
            if sig.startswith("sha256="):
                sig = sig.split("=", 1)[1]
            digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
            return hmac.compare_digest(sig, digest)
        except Exception:
            return False

