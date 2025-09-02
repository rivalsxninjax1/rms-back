from typing import Any, Dict, List, Optional, Union
from decimal import Decimal
from django.core.cache import cache
from django.conf import settings
from django.db.models import QuerySet
from django.core.serializers import serialize
from django.utils import timezone
import json
import logging

logger = logging.getLogger(__name__)


class CacheService:
    """
    Centralized caching service for the RMS application.
    Provides high-level caching operations with consistent key management.
    """
    
    # Cache prefixes
    MENU_PREFIX = "menu"
    USER_PREFIX = "user"
    ORDER_PREFIX = "order"
    RESERVATION_PREFIX = "reservation"
    INVENTORY_PREFIX = "inventory"
    ANALYTICS_PREFIX = "analytics"
    
    # Default timeouts
    SHORT_TIMEOUT = 300      # 5 minutes
    MEDIUM_TIMEOUT = 1800    # 30 minutes
    LONG_TIMEOUT = 3600      # 1 hour
    DAILY_TIMEOUT = 86400    # 24 hours
    
    @classmethod
    def _make_key(cls, prefix: str, *parts) -> str:
        """Generate a consistent cache key."""
        key_parts = [str(part) for part in parts if part is not None]
        return f"{prefix}:{"-".join(key_parts)}"
    
    @classmethod
    def get(cls, key: str, default=None) -> Any:
        """Get value from cache."""
        try:
            return cache.get(key, default)
        except Exception as e:
            logger.warning(f"Cache get failed for key {key}: {e}")
            return default
    
    @classmethod
    def set(cls, key: str, value: Any, timeout: int = MEDIUM_TIMEOUT) -> bool:
        """Set value in cache."""
        try:
            cache.set(key, value, timeout)
            return True
        except Exception as e:
            logger.warning(f"Cache set failed for key {key}: {e}")
            return False
    
    @classmethod
    def delete(cls, key: str) -> bool:
        """Delete value from cache."""
        try:
            cache.delete(key)
            return True
        except Exception as e:
            logger.warning(f"Cache delete failed for key {key}: {e}")
            return False
    
    @classmethod
    def delete_pattern(cls, pattern: str) -> int:
        """Delete all keys matching pattern."""
        try:
            # Check if we're using Redis cache backend
            if hasattr(cache._cache, 'get_client'):
                redis_client = cache._cache.get_client()
                key_prefix = settings.CACHES['default'].get('KEY_PREFIX', '')
                search_pattern = f"{key_prefix}:*{pattern}*" if key_prefix else f"*{pattern}*"
                keys = redis_client.keys(search_pattern)
                if keys:
                    redis_client.delete(*keys)
                    return len(keys)
            else:
                # For non-Redis backends (like LocMemCache/Dummy), pattern deletion isn't supported.
                # Quietly no-op to avoid log spam when caching is disabled.
                logger.debug(f"Pattern deletion not supported for current cache backend: {pattern}")
                return 0
        except Exception as e:
            logger.warning(f"Cache pattern delete failed for pattern {pattern}: {e}")
        return 0
    
    # Menu caching methods
    @classmethod
    def get_menu_items(cls, organization_id: int, category_id: Optional[int] = None) -> Optional[List[Dict]]:
        """Get cached menu items for an organization."""
        key = cls._make_key(cls.MENU_PREFIX, "items", organization_id, category_id or "all")
        return cls.get(key)
    
    @classmethod
    def set_menu_items(cls, organization_id: int, items: List[Dict], category_id: Optional[int] = None) -> bool:
        """Cache menu items for an organization."""
        key = cls._make_key(cls.MENU_PREFIX, "items", organization_id, category_id or "all")
        return cls.set(key, items, cls.LONG_TIMEOUT)
    
    @classmethod
    def get_menu_item(cls, item_id: int) -> Optional[Dict]:
        """Get cached menu item by ID."""
        key = cls._make_key(cls.MENU_PREFIX, "item", item_id)
        return cls.get(key)
    
    @classmethod
    def set_menu_item(cls, item_id: int, item_data: Dict) -> bool:
        """Cache menu item by ID."""
        key = cls._make_key(cls.MENU_PREFIX, "item", item_id)
        return cls.set(key, item_data, cls.LONG_TIMEOUT)
    
    @classmethod
    def invalidate_menu_cache(cls, organization_id: Optional[int] = None, item_id: Optional[int] = None):
        """Invalidate menu cache."""
        if item_id:
            cls.delete(cls._make_key(cls.MENU_PREFIX, "item", item_id))
        
        if organization_id:
            cls.delete_pattern(f"{cls.MENU_PREFIX}:items:{organization_id}")
        else:
            cls.delete_pattern(f"{cls.MENU_PREFIX}:*")
    
    # User caching methods
    @classmethod
    def get_user_profile(cls, user_id: int) -> Optional[Dict]:
        """Get cached user profile."""
        key = cls._make_key(cls.USER_PREFIX, "profile", user_id)
        return cls.get(key)
    
    @classmethod
    def set_user_profile(cls, user_id: int, profile_data: Dict) -> bool:
        """Cache user profile."""
        key = cls._make_key(cls.USER_PREFIX, "profile", user_id)
        return cls.set(key, profile_data, cls.MEDIUM_TIMEOUT)
    
    @classmethod
    def get_user_permissions(cls, user_id: int) -> Optional[List[str]]:
        """Get cached user permissions."""
        key = cls._make_key(cls.USER_PREFIX, "permissions", user_id)
        return cls.get(key)
    
    @classmethod
    def set_user_permissions(cls, user_id: int, permissions: List[str]) -> bool:
        """Cache user permissions."""
        key = cls._make_key(cls.USER_PREFIX, "permissions", user_id)
        return cls.set(key, permissions, cls.MEDIUM_TIMEOUT)
    
    @classmethod
    def invalidate_user_cache(cls, user_id: int):
        """Invalidate all cache for a user."""
        cls.delete_pattern(f"{cls.USER_PREFIX}:*:{user_id}")
    
    # Order caching methods
    @classmethod
    def get_cart(cls, session_key: str) -> Optional[Dict]:
        """Get cached cart data."""
        key = cls._make_key(cls.ORDER_PREFIX, "cart", session_key)
        return cls.get(key)
    
    @classmethod
    def set_cart(cls, session_key: str, cart_data: Dict) -> bool:
        """Cache cart data."""
        key = cls._make_key(cls.ORDER_PREFIX, "cart", session_key)
        return cls.set(key, cart_data, cls.MEDIUM_TIMEOUT)
    
    @classmethod
    def get_order_summary(cls, order_id: int) -> Optional[Dict]:
        """Get cached order summary."""
        key = cls._make_key(cls.ORDER_PREFIX, "summary", order_id)
        return cls.get(key)
    
    @classmethod
    def set_order_summary(cls, order_id: int, summary_data: Dict) -> bool:
        """Cache order summary."""
        key = cls._make_key(cls.ORDER_PREFIX, "summary", order_id)
        return cls.set(key, summary_data, cls.SHORT_TIMEOUT)
    
    @classmethod
    def invalidate_order_cache(cls, order_id: Optional[int] = None, session_key: Optional[str] = None):
        """Invalidate order cache."""
        if order_id:
            cls.delete_pattern(f"{cls.ORDER_PREFIX}:*:{order_id}")
        if session_key:
            cls.delete(cls._make_key(cls.ORDER_PREFIX, "cart", session_key))
    
    # Reservation caching methods
    @classmethod
    def get_available_tables(cls, location_id: int, date: str, time_slot: str) -> Optional[List[Dict]]:
        """Get cached available tables."""
        key = cls._make_key(cls.RESERVATION_PREFIX, "tables", location_id, date, time_slot)
        return cls.get(key)
    
    @classmethod
    def set_available_tables(cls, location_id: int, date: str, time_slot: str, tables: List[Dict]) -> bool:
        """Cache available tables."""
        key = cls._make_key(cls.RESERVATION_PREFIX, "tables", location_id, date, time_slot)
        return cls.set(key, tables, cls.SHORT_TIMEOUT)  # Short timeout for real-time data
    
    @classmethod
    def get_reservation_schedule(cls, location_id: int, date: str) -> Optional[Dict]:
        """Get cached reservation schedule."""
        key = cls._make_key(cls.RESERVATION_PREFIX, "schedule", location_id, date)
        return cls.get(key)
    
    @classmethod
    def set_reservation_schedule(cls, location_id: int, date: str, schedule: Dict) -> bool:
        """Cache reservation schedule."""
        key = cls._make_key(cls.RESERVATION_PREFIX, "schedule", location_id, date)
        return cls.set(key, schedule, cls.MEDIUM_TIMEOUT)
    
    @classmethod
    def invalidate_reservation_cache(cls, location_id: Optional[int] = None, date: Optional[str] = None):
        """Invalidate reservation cache."""
        if location_id and date:
            cls.delete_pattern(f"{cls.RESERVATION_PREFIX}:*:{location_id}:{date}")
        elif location_id:
            cls.delete_pattern(f"{cls.RESERVATION_PREFIX}:*:{location_id}")
        else:
            cls.delete_pattern(f"{cls.RESERVATION_PREFIX}:*")
    
    # Inventory caching methods
    @classmethod
    def get_inventory_levels(cls, organization_id: int) -> Optional[Dict]:
        """Get cached inventory levels."""
        key = cls._make_key(cls.INVENTORY_PREFIX, "levels", organization_id)
        return cls.get(key)
    
    @classmethod
    def set_inventory_levels(cls, organization_id: int, levels: Dict) -> bool:
        """Cache inventory levels."""
        key = cls._make_key(cls.INVENTORY_PREFIX, "levels", organization_id)
        return cls.set(key, levels, cls.MEDIUM_TIMEOUT)
    
    @classmethod
    def get_low_stock_items(cls, organization_id: int) -> Optional[List[Dict]]:
        """Get cached low stock items."""
        key = cls._make_key(cls.INVENTORY_PREFIX, "low_stock", organization_id)
        return cls.get(key)
    
    @classmethod
    def set_low_stock_items(cls, organization_id: int, items: List[Dict]) -> bool:
        """Cache low stock items."""
        key = cls._make_key(cls.INVENTORY_PREFIX, "low_stock", organization_id)
        return cls.set(key, items, cls.MEDIUM_TIMEOUT)
    
    @classmethod
    def invalidate_inventory_cache(cls, organization_id: int):
        """Invalidate inventory cache for organization."""
        cls.delete_pattern(f"{cls.INVENTORY_PREFIX}:*:{organization_id}")
    
    # Analytics caching methods
    @classmethod
    def get_daily_stats(cls, organization_id: int, date: str) -> Optional[Dict]:
        """Get cached daily statistics."""
        key = cls._make_key(cls.ANALYTICS_PREFIX, "daily", organization_id, date)
        return cls.get(key)
    
    @classmethod
    def set_daily_stats(cls, organization_id: int, date: str, stats: Dict) -> bool:
        """Cache daily statistics."""
        key = cls._make_key(cls.ANALYTICS_PREFIX, "daily", organization_id, date)
        return cls.set(key, stats, cls.DAILY_TIMEOUT)
    
    @classmethod
    def get_popular_items(cls, organization_id: int, period: str = "week") -> Optional[List[Dict]]:
        """Get cached popular items."""
        key = cls._make_key(cls.ANALYTICS_PREFIX, "popular", organization_id, period)
        return cls.get(key)
    
    @classmethod
    def set_popular_items(cls, organization_id: int, items: List[Dict], period: str = "week") -> bool:
        """Cache popular items."""
        key = cls._make_key(cls.ANALYTICS_PREFIX, "popular", organization_id, period)
        timeout = cls.DAILY_TIMEOUT if period == "day" else cls.DAILY_TIMEOUT * 7
        return cls.set(key, items, timeout)
    
    @classmethod
    def invalidate_analytics_cache(cls, organization_id: int):
        """Invalidate analytics cache for organization."""
        cls.delete_pattern(f"{cls.ANALYTICS_PREFIX}:*:{organization_id}")
    
    # Utility methods
    @classmethod
    def warm_cache(cls, organization_id: int):
        """Warm up cache with commonly accessed data."""
        logger.info(f"Warming cache for organization {organization_id}")
        
        # This would typically be called during off-peak hours
        # Implementation would fetch and cache commonly accessed data
        pass
    
    @classmethod
    def get_cache_stats(cls) -> Dict[str, Any]:
        """Get cache statistics."""
        try:
            redis_client = cache._cache.get_client()
            info = redis_client.info()
            return {
                'connected_clients': info.get('connected_clients', 0),
                'used_memory': info.get('used_memory_human', '0B'),
                'keyspace_hits': info.get('keyspace_hits', 0),
                'keyspace_misses': info.get('keyspace_misses', 0),
                'hit_rate': (
                    info.get('keyspace_hits', 0) / 
                    max(info.get('keyspace_hits', 0) + info.get('keyspace_misses', 0), 1)
                ) * 100
            }
        except Exception as e:
            logger.warning(f"Failed to get cache stats: {e}")
            return {}
    
    @classmethod
    def clear_all_cache(cls) -> bool:
        """Clear all cache (use with caution)."""
        try:
            cache.clear()
            logger.warning("All cache cleared")
            return True
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
            return False
