def menu_item(request: HttpRequest, item_id: int) -> HttpResponse:
    """
    Menu item detail page - fetches actual item from database.
    """
    from menu.models import MenuItem
    from django.shortcuts import get_object_or_404
    
    try:
        item = get_object_or_404(MenuItem, id=item_id, is_available=True)
        context = _ctx("menu-item", request, item_id=item_id)
        context.update({
            'item': item,
            'DEFAULT_CURRENCY': 'NPR',
        })
        return render(request, "storefront/menu_item.html", context)
    except Exception as e:
        # If item not found, redirect to menu
        return redirect("storefront:menu")
