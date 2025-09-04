"""drf-spectacular post-processing hooks.

Adds deprecation flags to legacy endpoints and optional metadata.
"""
from __future__ import annotations

from typing import Any, Dict


def _mark_op_deprecated(op: Dict[str, Any], reason: str, sunset: str | None = None) -> None:
    op["deprecated"] = True
    op.setdefault("description", "")
    if reason:
        op["description"] = (op["description"] + f"\n\nDeprecated: {reason}").strip()
    if sunset:
        op["x-sunset"] = sunset


def deprecate_paths_hook(result: Dict[str, Any], generator, request, public):
    """
    Post-process the generated schema to mark operations under legacy paths as deprecated.
    - /api/loyality/... → use /api/loyalty/...
    - /payments/webhook-legacy/ → use /payments/webhook/
    """
    paths = result.get("paths") or {}
    for path, methods in list(paths.items()):
        if not isinstance(methods, dict):
            continue

        is_legacy_loyalty = "/api/loyality/" in path
        is_legacy_webhook = path.endswith("/payments/webhook-legacy/") or path.endswith("/payments/webhook-legacy")

        if is_legacy_loyalty or is_legacy_webhook:
            reason = (
                "Use /api/loyalty/* instead." if is_legacy_loyalty else "Use /payments/webhook/ instead."
            )
            # sunset in ~90 days by default
            sunset = "2025-12-31"
            for method, op in methods.items():
                if method.lower() in {"get", "post", "put", "patch", "delete"} and isinstance(op, dict):
                    _mark_op_deprecated(op, reason=reason, sunset=sunset)

    # Add global extension for policy
    info = result.setdefault("info", {})
    info["x-sunset-policy"] = {
        "notice_period_days": 90,
        "contact": "security@yourdomain.example",
        "policy_url": "https://example.com/api-deprecation-policy",
    }
    return result

