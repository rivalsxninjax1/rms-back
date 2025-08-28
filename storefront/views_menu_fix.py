# Add this method to MenuItemsView in storefront/views.py
def get(self, request: HttpRequest) -> HttpResponse:
    from menu.models import MenuItem, MenuCategory
    
    # Fetch all available menu items with their categories
    items = MenuItem.objects.filter(is_available=True).select_related('category').order_by('sort_order', 'name')
    categories = MenuCategory.objects.filter(is_active=True).order_by('sort_order', 'name')
    
    context = _ctx("menu", request)
    context.update({
        'items': items,
        'categories': categories,
    })
    
    return render(request, self.template_name, context)
