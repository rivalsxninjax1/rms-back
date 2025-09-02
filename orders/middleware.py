# FILE: orders/middleware.py
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Optional

from django.conf import settings
from django.core import signing
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin

from orders.models import Cart
from orders.utils.cart import get_or_create_cart

logger = logging.getLogger(__name__)

# Signed cookie config (can be overridden in settings)
CART_COOKIE_NAME = getattr(settings, "CART_COOKIE_NAME", "rms_cart_uuid")
CART_COOKIE_MAX_AGE = getattr(settings, "CART_COOKIE_MAX_AGE", 60 * 60 * 24 * 30)  # 30 days
CART_COOKIE_SALT = getattr(settings, "CART_COOKIE_SALT", "rms.cart.cookie.v1")


def _get_signed_cart_uuid(request) -> Optional[str]:
    raw = request.COOKIES.get(CART_COOKIE_NAME)
    if not raw:
        return None
    try:
        return signing.loads(raw, salt=CART_COOKIE_SALT, max_age=CART_COOKIE_MAX_AGE)
    except Exception:
        return None


def _set_signed_cart_cookie(response, cart_uuid: str):
    value = signing.dumps(cart_uuid, salt=CART_COOKIE_SALT)
    secure = getattr(settings, "SESSION_COOKIE_SECURE", False)
    samesite = getattr(settings, "SESSION_COOKIE_SAMESITE", "Lax")
    domain = getattr(settings, "SESSION_COOKIE_DOMAIN", None)

    # Cart cookie must not be HttpOnly so the browser keeps it through navigation regardless of SSR
    response.set_cookie(
        CART_COOKIE_NAME,
        value,
        max_age=CART_COOKIE_MAX_AGE,
        secure=secure,
        httponly=False,
        samesite=samesite,
        domain=domain,
        path="/",
    )


class EnsureCartInitializedMiddleware(MiddlewareMixin):
    """
    Ensures that users have a cart initialized in their session and it persists across pages.
    - Uses your SessionCartManager for init/expiry/heartbeat
    - Adds a signed cart UUID cookie for guest users, allowing cart reattachment if session rotates
    - Clears expired carts via your manager (25 minutes inactivity)
    """

    CART_EXPIRY_MINUTES = 25  # kept from your code to work with SessionCartManager

    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)

    def __call__(self, request):
        # Skip cart ops for admin & docs
        if request.path.startswith("/admin/") or request.path.startswith("/api/docs/"):
            return self.get_response(request)

        # Ensure session exists
        if not hasattr(request, 'session') or not request.session.session_key:
            request.session.create()
        # Force browser to keep the session cookie on next response
        request.session.modified = True

        # ---------- Sticky reattach for guests ----------
        user = getattr(request, "user", None)
        is_authed = bool(user and user.is_authenticated)

        if not is_authed:
            signed_uuid = _get_signed_cart_uuid(request)
            if signed_uuid:
                # If this session has no active cart, reattach the cookie cart to this session
                has_active = Cart.objects.filter(
                    session_key=request.session.session_key, status=Cart.STATUS_ACTIVE
                ).exists()
                if not has_active:
                    cookie_cart = Cart.objects.filter(
                        cart_uuid=signed_uuid, status=Cart.STATUS_ACTIVE, user__isnull=True
                    ).first()
                    if cookie_cart and cookie_cart.session_key != request.session.session_key:
                        cookie_cart.session_key = request.session.session_key
                        cookie_cart.save(update_fields=["session_key", "updated_at"])
                        logger.debug(
                            "Reattached cookie cart %s to new session %s",
                            cookie_cart.cart_uuid,
                            request.session.session_key,
                        )

        # ---------- Expiration / Initialization ----------
        # Clean up expired carts (older than 25 minutes)
        expiry_time = timezone.now() - timedelta(minutes=self.CART_EXPIRY_MINUTES)
        Cart.objects.filter(
            updated_at__lt=expiry_time,
            status=Cart.STATUS_ACTIVE
        ).update(status=Cart.STATUS_EXPIRED)
        
        # Ensure user has an active cart
        cart_result = get_or_create_cart(request)
        logger.debug("Ensured cart %s for session: %s", cart_result.cart.cart_uuid, request.session.session_key)

        # Process the request
        response = self.get_response(request)

        # ---------- Mirror guest cart UUID into signed cookie ----------
        if not is_authed:
            active_cart = Cart.objects.filter(
                session_key=request.session.session_key, status=Cart.STATUS_ACTIVE
            ).order_by("-updated_at").first()
            if active_cart:
                _set_signed_cart_cookie(response, str(active_cart.cart_uuid))

        return response

    def process_request(self, request):
        # kept for compatibility; logic lives in __call__
        pass
