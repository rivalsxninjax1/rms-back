from django import template
from django.core.cache import cache
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from core.cache_service import CacheService
from core.cache_decorators import CacheHelper
import hashlib
import json

register = template.Library()


@register.simple_tag(takes_context=True)
def cache_fragment(context, fragment_name, timeout=300, *args):
    """
    Cache a template fragment.
    
    Usage:
    {% cache_fragment "menu_items" 3600 organization.id %}
    """
    cache_key = CacheHelper.get_fragment_key(fragment_name, *args)
    
    # Try to get from cache
    cached_content = cache.get(cache_key)
    if cached_content is not None:
        return mark_safe(cached_content)
    
    # If not in cache, return empty string (content will be rendered normally)
    return ""


@register.simple_tag
def cache_set_fragment(fragment_name, content, timeout=300, *args):
    """
    Set content in cache for a fragment.
    
    Usage:
    {% cache_set_fragment "menu_items" rendered_content 3600 organization.id %}
    """
    cache_key = CacheHelper.get_fragment_key(fragment_name, *args)
    cache.set(cache_key, content, timeout)
    return ""


@register.inclusion_tag('core/cached_menu_items.html', takes_context=True)
def cached_menu_items(context, organization_id, category_id=None):
    """
    Render cached menu items for a category.
    
    Usage:
    {% cached_menu_items organization.id category.id %}
    """
    from orders.cache_utils import get_menu_categories_cached
    
    # Get cached menu items
    menu_items = CacheService.get_menu_items(organization_id, category_id)
    
    if menu_items is None:
        # Fallback to database if not cached
        from menu.models import MenuItem
        queryset = MenuItem.objects.filter(
            organization_id=organization_id,
            is_available=True
        )
        
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        
        menu_items = list(queryset.values(
            'id', 'name', 'description', 'price', 'image',
            'is_vegetarian', 'preparation_time'
        ))
        
        # Cache the result
        CacheService.set_menu_items(organization_id, menu_items, category_id)
    
    return {
        'menu_items': menu_items,
        'request': context['request']
    }


@register.inclusion_tag('core/cached_popular_items.html', takes_context=True)
def cached_popular_items(context, organization_id, limit=5):
    """
    Render cached popular items.
    
    Usage:
    {% cached_popular_items organization.id 10 %}
    """
    from orders.cache_utils import get_popular_items_cached
    
    popular_items = get_popular_items_cached(organization_id, limit)
    
    return {
        'popular_items': popular_items,
        'request': context['request']
    }


@register.simple_tag
def cache_user_data(user_id, data_type):
    """
    Get cached user data.
    
    Usage:
    {% cache_user_data user.id "profile" as user_profile %}
    """
    if data_type == 'profile':
        return CacheService.get_user_profile(user_id)
    elif data_type == 'permissions':
        return CacheService.get_user_permissions(user_id)
    return None


@register.simple_tag
def cache_stats():
    """
    Get cache statistics for debugging.
    
    Usage:
    {% cache_stats as stats %}
    """
    return CacheService.get_cache_stats()


@register.filter
def cache_key_for(obj, prefix="obj"):
    """
    Generate a cache key for an object.
    
    Usage:
    {{ menu_item|cache_key_for:"menu_item" }}
    """
    if hasattr(obj, 'id'):
        return f"{prefix}:{obj.id}"
    elif hasattr(obj, 'pk'):
        return f"{prefix}:{obj.pk}"
    else:
        return f"{prefix}:{hash(str(obj))}"


@register.simple_tag(takes_context=True)
def cache_vary_on_user(context):
    """
    Generate cache key variation based on user.
    
    Usage:
    {% cache_vary_on_user as user_key %}
    """
    request = context.get('request')
    if request and hasattr(request, 'user') and request.user.is_authenticated:
        return f"user:{request.user.id}"
    return "anonymous"


@register.simple_tag
def cache_invalidate(pattern):
    """
    Invalidate cache pattern (for admin use).
    
    Usage:
    {% cache_invalidate "menu:*" %}
    """
    return CacheService.delete_pattern(pattern)


@register.inclusion_tag('core/cache_debug.html', takes_context=True)
def cache_debug_info(context):
    """
    Show cache debug information (only in DEBUG mode).
    
    Usage:
    {% cache_debug_info %}
    """
    from django.conf import settings
    
    if not settings.DEBUG:
        return {'show_debug': False}
    
    stats = CacheService.get_cache_stats()
    
    return {
        'show_debug': True,
        'cache_stats': stats,
        'request': context.get('request')
    }


@register.simple_tag
def cache_version():
    """
    Get current cache version for cache busting.
    
    Usage:
    {% cache_version as version %}
    """
    from django.conf import settings
    return getattr(settings, 'CACHE_VERSION', 1)


@register.filter
def cached_image_url(image_field, size="medium"):
    """
    Get cached image URL with optional size parameter.
    
    Usage:
    {{ menu_item.image|cached_image_url:"large" }}
    """
    if not image_field:
        return ""
    
    cache_key = f"image_url:{image_field.name}:{size}"
    cached_url = cache.get(cache_key)
    
    if cached_url is not None:
        return cached_url
    
    # Generate URL (in a real app, you might have different sizes)
    url = image_field.url if image_field else ""
    
    # Cache for 1 hour
    cache.set(cache_key, url, 3600)
    return url


@register.simple_tag
def cache_menu_search(organization_id, query, category_id=None):
    """
    Cached menu search results.
    
    Usage:
    {% cache_menu_search organization.id "pizza" category.id as search_results %}
    """
    from orders.cache_utils import search_menu_items_cached
    return search_menu_items_cached(organization_id, query, category_id)