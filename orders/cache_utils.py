from typing import Dict, List, Any, Tuple, Optional
from decimal import Decimal
from django.core.cache import cache
from django.conf import settings
from menu.models import MenuItem, Modifier
from core.cache_service import CacheService
from core.cache_decorators import cache_result, cache_menu_data

# Cache timeouts (in seconds)
MENU_ITEM_CACHE_TIMEOUT = getattr(settings, 'MENU_ITEM_CACHE_TIMEOUT', 3600)  # 1 hour
MODIFIER_CACHE_TIMEOUT = getattr(settings, 'MODIFIER_CACHE_TIMEOUT', 3600)  # 1 hour


def get_menu_item_cached(item_id: int) -> Optional[Tuple[str, Decimal, Optional[str]]]:
    """
    Get menu item details (name, price, image_url) from cache or database.
    Returns tuple of (name, price, image_url) or None if not found.
    """
    cache_key = f"menu_item_{item_id}"
    cached_data = cache.get(cache_key)
    
    if cached_data is not None:
        return cached_data
    
    try:
        menu_item = MenuItem.objects.select_related('category').get(id=item_id, is_available=True)
        image_url = menu_item.image.url if menu_item.image else None
        data = (menu_item.name, menu_item.price, image_url)
        cache.set(cache_key, data, MENU_ITEM_CACHE_TIMEOUT)
        return data
    except MenuItem.DoesNotExist:
        # Cache negative result for shorter time to avoid repeated DB hits
        cache.set(cache_key, None, 300)  # 5 minutes
        return None


def get_menu_items_batch_cached(item_ids: List[int]) -> Dict[int, Tuple[str, Decimal, Optional[str]]]:
    """
    Get multiple menu items from cache or database in batch.
    Returns dict mapping item_id to (name, price, image_url).
    """
    if not item_ids:
        return {}
    
    # Try to get from cache first
    cache_keys = [f"menu_item_{item_id}" for item_id in item_ids]
    cached_items = cache.get_many(cache_keys)
    
    result = {}
    missing_ids = []
    
    # Process cached results
    for item_id in item_ids:
        cache_key = f"menu_item_{item_id}"
        if cache_key in cached_items:
            cached_data = cached_items[cache_key]
            if cached_data is not None:
                result[item_id] = cached_data
        else:
            missing_ids.append(item_id)
    
    # Fetch missing items from database
    if missing_ids:
        menu_items = MenuItem.objects.filter(
            id__in=missing_ids, 
            is_available=True
        ).select_related('category')
        
        cache_data = {}
        for menu_item in menu_items:
            image_url = menu_item.image.url if menu_item.image else None
            data = (menu_item.name, menu_item.price, image_url)
            result[menu_item.id] = data
            cache_data[f"menu_item_{menu_item.id}"] = data
        
        # Cache the fetched items
        if cache_data:
            cache.set_many(cache_data, MENU_ITEM_CACHE_TIMEOUT)
        
        # Cache negative results for items not found
        found_ids = {item.id for item in menu_items}
        for item_id in missing_ids:
            if item_id not in found_ids:
                cache.set(f"menu_item_{item_id}", None, 300)  # 5 minutes
    
    return result


def get_modifiers_batch_cached(modifier_ids: List[int]) -> Dict[int, Tuple[str, Decimal]]:
    """
    Get multiple modifiers from cache or database in batch.
    Returns dict mapping modifier_id to (name, price).
    """
    if not modifier_ids:
        return {}
    
    # Try to get from cache first
    cache_keys = [f"modifier_{modifier_id}" for modifier_id in modifier_ids]
    cached_modifiers = cache.get_many(cache_keys)
    
    result = {}
    missing_ids = []
    
    # Process cached results
    for modifier_id in modifier_ids:
        cache_key = f"modifier_{modifier_id}"
        if cache_key in cached_modifiers:
            cached_data = cached_modifiers[cache_key]
            if cached_data is not None:
                result[modifier_id] = cached_data
        else:
            missing_ids.append(modifier_id)
    
    # Fetch missing modifiers from database
    if missing_ids:
        modifiers = Modifier.objects.filter(
            id__in=missing_ids, 
            is_available=True
        ).select_related('modifier_group')
        
        cache_data = {}
        for modifier in modifiers:
            data = (modifier.name, modifier.price)
            result[modifier.id] = data
            cache_data[f"modifier_{modifier.id}"] = data
        
        # Cache the fetched modifiers
        if cache_data:
            cache.set_many(cache_data, MODIFIER_CACHE_TIMEOUT)
        
        # Cache negative results for modifiers not found
        found_ids = {modifier.id for modifier in modifiers}
        for modifier_id in missing_ids:
            if modifier_id not in found_ids:
                cache.set(f"modifier_{modifier_id}", None, 300)  # 5 minutes
    
    return result


def invalidate_menu_item_cache(item_id: int):
    """
    Invalidate cache for a specific menu item.
    Call this when menu item is updated.
    """
    cache.delete(f"menu_item_{item_id}")


def invalidate_modifier_cache(modifier_id: int):
    """
    Invalidate cache for a specific modifier.
    Call this when modifier is updated.
    """
    cache.delete(f"modifier_{modifier_id}")


def clear_menu_cache():
    """
    Clear all menu-related cache.
    Use sparingly, only when doing bulk updates.
    """
    CacheService.invalidate_menu_cache()


@cache_menu_data(timeout=MENU_ITEM_CACHE_TIMEOUT)
def get_menu_categories_cached(organization_id: int) -> List[Dict[str, Any]]:
    """
    Get menu categories with item counts from cache or database.
    """
    from menu.models import Category
    
    categories = Category.objects.filter(
        organization_id=organization_id,
        is_active=True
    ).prefetch_related('menu_items').order_by('sort_order', 'name')
    
    result = []
    for category in categories:
        available_items = category.menu_items.filter(is_available=True).count()
        result.append({
            'id': category.id,
            'name': category.name,
            'description': category.description,
            'image_url': category.image.url if category.image else None,
            'sort_order': category.sort_order,
            'item_count': available_items
        })
    
    return result


@cache_menu_data(timeout=MENU_ITEM_CACHE_TIMEOUT)
def get_popular_items_cached(organization_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get popular menu items from cache or calculate from order data.
    """
    from django.db.models import Count, Sum
    from orders.models import OrderItem
    
    # Get popular items based on order frequency in last 30 days
    from datetime import datetime, timedelta
    thirty_days_ago = datetime.now() - timedelta(days=30)
    
    popular_items = MenuItem.objects.filter(
        organization_id=organization_id,
        is_available=True,
        order_items__order__created_at__gte=thirty_days_ago
    ).annotate(
        order_count=Count('order_items'),
        total_quantity=Sum('order_items__quantity')
    ).order_by('-order_count', '-total_quantity')[:limit]
    
    result = []
    for item in popular_items:
        result.append({
            'id': item.id,
            'name': item.name,
            'price': float(item.price),
            'image_url': item.image.url if item.image else None,
            'order_count': item.order_count,
            'total_quantity': item.total_quantity
        })
    
    return result


@cache_result(timeout=1800, key_prefix='menu_search')  # 30 minutes
def search_menu_items_cached(organization_id: int, query: str, category_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Search menu items with caching.
    """
    from django.db.models import Q
    
    queryset = MenuItem.objects.filter(
        organization_id=organization_id,
        is_available=True
    )
    
    if category_id:
        queryset = queryset.filter(category_id=category_id)
    
    if query:
        queryset = queryset.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(category__name__icontains=query)
        )
    
    queryset = queryset.select_related('category').order_by('name')
    
    result = []
    for item in queryset:
        result.append({
            'id': item.id,
            'name': item.name,
            'description': item.description,
            'price': float(item.price),
            'image_url': item.image.url if item.image else None,
            'category': {
                'id': item.category.id,
                'name': item.category.name
            } if item.category else None,
            'is_vegetarian': item.is_vegetarian,
            'preparation_time': item.preparation_time
        })
    
    return result


def invalidate_menu_search_cache(organization_id: int):
    """
    Invalidate menu search cache for an organization.
    """
    CacheService.delete_pattern(f"menu_search:*:{organization_id}:*")


def get_cart_totals_cached(cart_items: List[Dict]) -> Dict[str, Decimal]:
    """
    Calculate cart totals with caching for menu item prices.
    """
    if not cart_items:
        return {
            'subtotal': Decimal('0.00'),
            'tax': Decimal('0.00'),
            'total': Decimal('0.00')
        }
    
    # Extract all item and modifier IDs
    item_ids = [item['menu_item_id'] for item in cart_items]
    modifier_ids = []
    for item in cart_items:
        if 'modifiers' in item:
            modifier_ids.extend([mod['modifier_id'] for mod in item['modifiers']])
    
    # Get cached data
    menu_items = get_menu_items_batch_cached(item_ids)
    modifiers = get_modifiers_batch_cached(modifier_ids) if modifier_ids else {}
    
    subtotal = Decimal('0.00')
    
    for cart_item in cart_items:
        item_id = cart_item['menu_item_id']
        quantity = cart_item.get('quantity', 1)
        
        if item_id in menu_items:
            item_price = menu_items[item_id][1]  # Price is second element in tuple
            item_total = item_price * quantity
            
            # Add modifier prices
            if 'modifiers' in cart_item:
                for modifier_data in cart_item['modifiers']:
                    modifier_id = modifier_data['modifier_id']
                    if modifier_id in modifiers:
                        modifier_price = modifiers[modifier_id][1]
                        item_total += modifier_price * quantity
            
            subtotal += item_total
    
    # Calculate tax (assuming 8.5% tax rate, should be configurable)
    tax_rate = Decimal(getattr(settings, 'DEFAULT_TAX_RATE', '0.085'))
    tax = (subtotal * tax_rate).quantize(Decimal('0.01'))
    total = subtotal + tax
    
    return {
        'subtotal': subtotal,
        'tax': tax,
        'total': total
    }