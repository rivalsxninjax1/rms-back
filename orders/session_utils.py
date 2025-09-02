# orders/session_utils.py
"""
Comprehensive session management utilities for cart functionality.
Handles session initialization, validation, cleanup, and persistence
for both authenticated and anonymous users.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

from django.contrib.sessions.models import Session
from django.contrib.auth.models import AnonymousUser
from django.http import HttpRequest
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger(__name__)


class SessionCartManager:
    """
    Centralized session cart management with robust error handling,
    validation, and persistence across different user states.
    """
    
    # Session keys used for cart data
    CART_KEYS = [
        "cart", "cart_meta", "applied_coupon", "cart_last_activity",
        "cart_last_modified", "_cart_init_done", "cart_expired",
        "server_cart_v1"  # Menu app's cart key
    ]
    
    # Default cart expiration time (minutes)
    CART_EXPIRY_MINUTES = 25
    
    def __init__(self, request: HttpRequest):
        self.request = request
        self.session = getattr(request, 'session', None)
        self.user = getattr(request, 'user', None)
    
    def ensure_session_exists(self) -> bool:
        """
        Ensure session exists and is properly initialized.
        Returns True if session is available, False otherwise.
        """
        try:
            if not self.session:
                logger.warning("No session available on request")
                return False
            
            # Force session creation if it doesn't have a key
            if not self.session.session_key:
                self.session.create()
                logger.debug(f"Created new session: {self.session.session_key}")
            
            return True
        except Exception as e:
            logger.error(f"Failed to ensure session exists: {e}")
            return False
    
    def initialize_cart(self, force: bool = False) -> bool:
        """
        Initialize cart in session with proper defaults.
        
        Args:
            force: If True, reinitialize even if already done
            
        Returns:
            True if initialization successful, False otherwise
        """
        try:
            if not self.ensure_session_exists():
                return False
            
            # Check if already initialized (unless forcing)
            if not force and self.session.get("_cart_init_done", False):
                # Ensure cart exists even if init flag is set (defensive)
                modified = False
                if "cart" not in self.session:
                    self.session["cart"] = []
                    modified = True
                if "cart_meta" not in self.session:
                    self.session["cart_meta"] = {}
                    modified = True
                if modified:
                    self.session.modified = True
                return True

            # Initialize cart data (only when not already initialized)
            self.session["cart"] = []
            self.session["cart_meta"] = {}
            self.session["_cart_init_done"] = True
            self.session["cart_last_activity"] = timezone.now().isoformat()
            self.session.modified = True
            
            logger.debug(f"Initialized cart for session: {self.session.session_key}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize cart: {e}")
            return False
    
    def clear_cart(self, reinitialize: bool = True) -> bool:
        """
        Clear all cart-related session data.
        
        Args:
            reinitialize: If True, reinitialize empty cart after clearing
            
        Returns:
            True if clearing successful, False otherwise
        """
        try:
            if not self.ensure_session_exists():
                return False
            
            # Clear all cart-related keys
            for key in self.CART_KEYS:
                self.session.pop(key, None)
            
            # Reinitialize if requested
            if reinitialize:
                self.session["cart"] = []
                self.session["cart_meta"] = {}
                self.session["_cart_init_done"] = True
                self.session["cart_last_activity"] = timezone.now().isoformat()
            
            self.session.modified = True
            self.session.save()
            
            logger.debug(f"Cleared cart for session: {self.session.session_key}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to clear cart: {e}")
            return False
    
    def update_activity(self) -> bool:
        """
        Update cart last activity timestamp.
        
        Returns:
            True if update successful, False otherwise
        """
        try:
            if not self.ensure_session_exists():
                return False
            
            self.session["cart_last_activity"] = timezone.now().isoformat()
            self.session.modified = True
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update cart activity: {e}")
            return False
    
    def is_cart_expired(self) -> bool:
        """
        Check if cart has expired based on last activity.
        
        Returns:
            True if cart is expired, False otherwise
        """
        try:
            if not self.session:
                return True
            
            last_activity = self.session.get('cart_last_activity')
            if not last_activity:
                return False  # No activity recorded, not expired
            
            last_activity_time = timezone.datetime.fromisoformat(last_activity)
            expiry_time = last_activity_time + timedelta(minutes=self.CART_EXPIRY_MINUTES)
            
            return timezone.now() > expiry_time
            
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid cart activity timestamp: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to check cart expiration: {e}")
            return False
    
    def get_cart_data(self) -> Dict[str, Any]:
        """
        Get cart data with validation and defaults.

        Returns:
            Dictionary containing cart data with proper defaults
        """
        try:
            if not self.session:
                return self._get_default_cart_data()
            
            cart_items = self.session.get("cart", [])
            if not isinstance(cart_items, list):
                cart_items = []
            
            cart_meta = self.session.get("cart_meta", {})
            if not isinstance(cart_meta, dict):
                cart_meta = {}
            
            return {
                "items": cart_items,
                "meta": cart_meta,
                "last_activity": self.session.get("cart_last_activity"),
                "last_modified": self.session.get("cart_last_modified"),
                "applied_coupon": self.session.get("applied_coupon"),
                "expired": self.is_cart_expired()
            }
            
        except Exception as e:
            logger.error(f"Failed to get cart data: {e}")
            return self._get_default_cart_data()
    
    def get_cart_items(self) -> List[Dict[str, Any]]:
        """
        Get cart items with validation.
        
        Returns:
            List of cart items with proper defaults
        """
        try:
            if not self.session:
                print(f"DEBUG SessionCartManager: No session available")
                return []
            
            print(f"DEBUG SessionCartManager: Session key: {self.session.session_key}")
            print(f"DEBUG SessionCartManager: Session data keys: {list(self.session.keys())}")
            
            cart_items = self.session.get("cart", [])
            print(f"DEBUG SessionCartManager: Raw cart items: {cart_items}")
            
            if not isinstance(cart_items, list):
                print(f"DEBUG SessionCartManager: Cart items not a list, type: {type(cart_items)}")
                return []
            
            print(f"DEBUG SessionCartManager: Returning {len(cart_items)} cart items")
            return cart_items
            
        except Exception as e:
            logger.error(f"Failed to get cart items: {e}")
            return []
    
    def get_cart_meta(self) -> Dict[str, Any]:
        """
        Get cart metadata with validation.
        
        Returns:
            Dictionary containing cart metadata with proper defaults
        """
        try:
            if not self.session:
                return {}
            
            cart_meta = self.session.get("cart_meta", {})
            if not isinstance(cart_meta, dict):
                return {}
            
            return cart_meta
            
        except Exception as e:
            logger.error(f"Failed to get cart meta: {e}")
            return {}
    
    def set_cart_data(self, items: List[Dict[str, Any]], meta: Optional[Dict[str, Any]] = None) -> bool:
        """
        Set cart data with validation.
        
        Args:
            items: List of cart items
            meta: Optional cart metadata
            
        Returns:
            True if setting successful, False otherwise
        """
        try:
            if not self.ensure_session_exists():
                return False
            
            # Validate items
            if not isinstance(items, list):
                items = []
            
            # Validate meta
            if meta is None:
                meta = {}
            elif not isinstance(meta, dict):
                meta = {}
            
            # Set data
            self.session["cart"] = items
            self.session["cart_meta"] = meta
            self.session["cart_last_modified"] = timezone.now().isoformat()
            self.session["cart_last_activity"] = timezone.now().isoformat()
            self.session.modified = True
            
            # Explicitly save the session
            self.session.save()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to set cart data: {e}")
            return False
    
    def _get_default_cart_data(self) -> Dict[str, Any]:
        """Get default cart data structure."""
        return {
            "items": [],
            "meta": {},
            "last_activity": None,
            "last_modified": None,
            "applied_coupon": None,
            "expired": False
        }
    
    @classmethod
    def clear_user_sessions(cls, user) -> int:
        """
        Clear cart data from all sessions belonging to a specific user.
        Used after successful payment or logout.
        
        Args:
            user: User instance
            
        Returns:
            Number of sessions cleared
        """
        if not user or isinstance(user, AnonymousUser):
            return 0
        
        cleared_count = 0
        
        try:
            # Get all active sessions
            sessions = Session.objects.filter(expire_date__gte=timezone.now())
            
            for session in sessions:
                try:
                    session_data = session.get_decoded()
                    
                    # Check if this session belongs to our user
                    if session_data.get('_auth_user_id') == str(user.id):
                        # Clear cart-related session data
                        session_modified = False
                        for key in cls.CART_KEYS:
                            if key in session_data:
                                del session_data[key]
                                session_modified = True
                        
                        # Re-initialize empty cart
                        if session_modified:
                            session_data['cart'] = []
                            session_data['cart_meta'] = {}
                            session_data['_cart_init_done'] = True
                            session_data['cart_last_activity'] = timezone.now().isoformat()
                            
                            # Save the updated session
                            session.session_data = session.encode(session_data)
                            session.save()
                            cleared_count += 1
                            
                except Exception as e:
                    logger.warning(f"Failed to clear cart from session {session.session_key}: {e}")
                    continue
            
            logger.info(f"Cleared cart data from {cleared_count} sessions for user {user.id}")
            return cleared_count
            
        except Exception as e:
            logger.error(f"Failed to clear user sessions for user {user.id}: {e}")
            return 0


def get_session_cart_manager(request: HttpRequest) -> SessionCartManager:
    """
    Factory function to get a SessionCartManager instance.
    
    Args:
        request: HTTP request object
        
    Returns:
        SessionCartManager instance
    """
    return SessionCartManager(request)


def ensure_cart_initialized(request: HttpRequest) -> bool:
    """
    Convenience function to ensure cart is initialized for a request.
    
    Args:
        request: HTTP request object
        
    Returns:
        True if initialization successful, False otherwise
    """
    manager = get_session_cart_manager(request)
    return manager.initialize_cart()


def clear_cart_session(request: HttpRequest) -> bool:
    """
    Convenience function to clear cart session data.
    
    Args:
        request: HTTP request object
        
    Returns:
        True if clearing successful, False otherwise
    """
    manager = get_session_cart_manager(request)
    return manager.clear_cart()