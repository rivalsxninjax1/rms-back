from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from menu.models import MenuItem, Modifier
from .cache_utils import invalidate_menu_item_cache, invalidate_modifier_cache


@receiver(post_save, sender=MenuItem)
def invalidate_menu_item_on_save(sender, instance, **kwargs):
    """
    Invalidate menu item cache when a menu item is saved.
    """
    invalidate_menu_item_cache(instance.id)


@receiver(post_delete, sender=MenuItem)
def invalidate_menu_item_on_delete(sender, instance, **kwargs):
    """
    Invalidate menu item cache when a menu item is deleted.
    """
    invalidate_menu_item_cache(instance.id)


@receiver(post_save, sender=Modifier)
def invalidate_modifier_on_save(sender, instance, **kwargs):
    """
    Invalidate modifier cache when a modifier is saved.
    """
    invalidate_modifier_cache(instance.id)


@receiver(post_delete, sender=Modifier)
def invalidate_modifier_on_delete(sender, instance, **kwargs):
    """
    Invalidate modifier cache when a modifier is deleted.
    """
    invalidate_modifier_cache(instance.id)