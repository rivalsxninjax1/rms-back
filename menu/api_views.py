from decimal import Decimal
from django.db.models import Q, Prefetch
from django.utils import timezone
from django.core.cache import cache
from django.http import Http404
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend

from .models import MenuCategory, MenuItem, ModifierGroup, Modifier
from .serializers import (
    MenuCategorySerializer, MenuCategoryWithItemsSerializer,
    MenuItemSerializer, MenuItemListSerializer, MenuItemDetailSerializer,
    ModifierGroupSerializer, ModifierSerializer,
    MenuDisplaySerializer, MenuSearchSerializer
)


class StandardResultsSetPagination(PageNumberPagination):
    """Standard pagination for API responses."""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class MenuCategoryViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing menu categories with proper CRUD operations.
    """
    queryset = MenuCategory.objects.all().order_by('sort_order', 'name')
    serializer_class = MenuCategorySerializer
    permission_classes = [AllowAny]  # Public read access
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'sort_order', 'created_at']
    ordering = ['sort_order', 'name']
    
    def get_queryset(self):
        """Filter queryset based on user permissions."""
        queryset = super().get_queryset()
        
        # For public access, only show active categories
        if not self.request.user.is_authenticated or not self.request.user.is_staff:
            queryset = queryset.filter(is_active=True)
        
        return queryset
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'with_items':
            return MenuCategoryWithItemsSerializer
        return super().get_serializer_class()
    
    @action(detail=False, methods=['get'])
    def with_items(self, request):
        """
        Get all active categories with their available menu items.
        Useful for displaying the complete menu.
        """
        # Check cache first
        cache_key = 'menu_categories_with_items'
        cached_data = cache.get(cache_key)
        
        if cached_data is None:
            # Prefetch related data for efficiency
            queryset = self.get_queryset().filter(is_active=True).prefetch_related(
                Prefetch(
                    'menu_items',
                    queryset=MenuItem.objects.filter(is_available=True).order_by('sort_order', 'name')
                )
            )
            
            serializer = self.get_serializer(queryset, many=True)
            cached_data = serializer.data
            
            # Cache for 15 minutes
            cache.set(cache_key, cached_data, 60 * 15)
        
        return Response(cached_data)
    
    @action(detail=True, methods=['get'])
    def items(self, request, pk=None):
        """
        Get all available menu items for a specific category.
        """
        category = self.get_object()
        items = MenuItem.objects.filter(
            category=category,
            is_available=True
        ).order_by('sort_order', 'name')
        
        # Apply pagination
        page = self.paginate_queryset(items)
        if page is not None:
            serializer = MenuItemListSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        
        serializer = MenuItemListSerializer(items, many=True, context={'request': request})
        return Response(serializer.data)


class MenuItemViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing menu items with comprehensive CRUD operations.
    """
    queryset = MenuItem.objects.select_related('category').prefetch_related(
        'modifier_groups__modifiers'
    ).all().order_by('sort_order', 'name')
    permission_classes = [AllowAny]  # Public read access
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = [
        'category', 'is_available', 'is_featured', 'is_vegan', 'is_gluten_free'
    ]
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'price', 'sort_order', 'created_at']
    ordering = ['sort_order', 'name']
    
    def get_queryset(self):
        """Filter queryset based on user permissions and request parameters."""
        queryset = super().get_queryset()
        
        # For public access, only show available items
        if not self.request.user.is_authenticated or not self.request.user.is_staff:
            queryset = queryset.filter(is_available=True)
        
        # Filter by price range if provided
        min_price = self.request.query_params.get('min_price')
        max_price = self.request.query_params.get('max_price')
        
        if min_price:
            try:
                queryset = queryset.filter(price__gte=Decimal(min_price))
            except (ValueError, TypeError):
                pass
        
        if max_price:
            try:
                queryset = queryset.filter(price__lte=Decimal(max_price))
            except (ValueError, TypeError):
                pass
        
        return queryset
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'list':
            return MenuItemListSerializer
        elif self.action == 'retrieve':
            return MenuItemDetailSerializer
        return MenuItemSerializer
    
    @action(detail=False, methods=['get'])
    def featured(self, request):
        """
        Get all featured menu items.
        """
        items = self.get_queryset().filter(is_featured=True)
        
        page = self.paginate_queryset(items)
        if page is not None:
            serializer = MenuItemListSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        
        serializer = MenuItemListSerializer(items, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def search(self, request):
        """
        Advanced search for menu items with multiple filters.
        """
        serializer = MenuSearchSerializer(data=request.query_params)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        validated_data = serializer.validated_data
        query = validated_data['query']
        
        # Build search query
        queryset = self.get_queryset().filter(
            Q(name__icontains=query) | 
            Q(description__icontains=query)
        )
        
        # Apply additional filters
        if 'category_id' in validated_data and validated_data['category_id']:
            queryset = queryset.filter(category_id=validated_data['category_id'])
        
        if 'is_vegan' in validated_data:
            queryset = queryset.filter(is_vegan=validated_data['is_vegan'])
        
        if 'is_gluten_free' in validated_data:
            queryset = queryset.filter(is_gluten_free=validated_data['is_gluten_free'])
        
        if 'min_price' in validated_data:
            queryset = queryset.filter(price__gte=validated_data['min_price'])
        
        if 'max_price' in validated_data:
            queryset = queryset.filter(price__lte=validated_data['max_price'])
        
        # Order by relevance (items with query in name first)
        queryset = queryset.extra(
            select={
                'name_match': "CASE WHEN LOWER(name) LIKE LOWER(%s) THEN 1 ELSE 0 END"
            },
            select_params=[f'%{query}%']
        ).order_by('-name_match', 'sort_order', 'name')
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = MenuItemListSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        
        serializer = MenuItemListSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def modifiers(self, request, pk=None):
        """
        Get all modifier groups for a specific menu item.
        """
        menu_item = self.get_object()
        modifier_groups = menu_item.modifier_groups.prefetch_related('modifiers').all()
        
        serializer = ModifierGroupSerializer(
            modifier_groups, many=True, context={'request': request}
        )
        return Response(serializer.data)


class ModifierGroupViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing modifier groups.
    """
    queryset = ModifierGroup.objects.prefetch_related('modifiers').all().order_by('sort_order', 'name')
    serializer_class = ModifierGroupSerializer
    permission_classes = [AllowAny]  # Public read access
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_required']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'sort_order', 'created_at']
    ordering = ['sort_order', 'name']
    
    @action(detail=True, methods=['get'])
    def modifiers(self, request, pk=None):
        """
        Get all modifiers for a specific modifier group.
        """
        modifier_group = self.get_object()
        modifiers = modifier_group.modifiers.filter(is_available=True).order_by('sort_order', 'name')
        
        serializer = ModifierSerializer(modifiers, many=True, context={'request': request})
        return Response(serializer.data)


class ModifierViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing individual modifiers.
    """
    queryset = Modifier.objects.all().order_by('sort_order', 'name')
    serializer_class = ModifierSerializer
    permission_classes = [AllowAny]  # Public read access
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_available', 'modifier_group']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'price', 'sort_order', 'created_at']
    ordering = ['sort_order', 'name']
    
    def get_queryset(self):
        """Filter queryset based on user permissions."""
        queryset = super().get_queryset()
        
        # For public access, only show available modifiers
        if not self.request.user.is_authenticated or not self.request.user.is_staff:
            queryset = queryset.filter(is_available=True)
        
        return queryset


class MenuDisplayViewSet(viewsets.ViewSet):
    """
    ViewSet for displaying the complete menu structure.
    Optimized for frontend consumption.
    """
    permission_classes = [AllowAny]
    
    def list(self, request):
        """
        Get the complete menu display with categories, items, and featured items.
        """
        # Check cache first
        cache_key = 'complete_menu_display'
        cached_data = cache.get(cache_key)
        
        if cached_data is None:
            # Get active categories with their available items
            categories = MenuCategory.objects.filter(is_active=True).prefetch_related(
                Prefetch(
                    'menu_items',
                    queryset=MenuItem.objects.filter(is_available=True).order_by('sort_order', 'name')
                )
            ).order_by('sort_order', 'name')
            
            # Get featured items
            featured_items = MenuItem.objects.filter(
                is_available=True, is_featured=True
            ).select_related('category').order_by('sort_order', 'name')[:10]
            
            # Prepare data
            menu_data = {
                'categories': MenuCategoryWithItemsSerializer(
                    categories, many=True, context={'request': request}
                ).data,
                'featured_items': MenuItemListSerializer(
                    featured_items, many=True, context={'request': request}
                ).data,
                'total_categories': categories.count(),
                'total_items': MenuItem.objects.filter(is_available=True).count(),
                'last_updated': timezone.now()
            }
            
            serializer = MenuDisplaySerializer(menu_data)
            cached_data = serializer.data
            
            # Cache for 30 minutes
            cache.set(cache_key, cached_data, 60 * 30)
        
        return Response(cached_data)
    
    @action(detail=False, methods=['post'])
    def clear_cache(self, request):
        """
        Clear menu cache. Useful after menu updates.
        Requires staff permissions.
        """
        if not request.user.is_authenticated or not request.user.is_staff:
            return Response(
                {'error': 'Permission denied'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        cache_keys = [
            'complete_menu_display',
            'menu_categories_with_items'
        ]
        
        for key in cache_keys:
            cache.delete(key)
        
        return Response({'message': 'Menu cache cleared successfully'})
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Get menu statistics.
        """
        stats = {
            'total_categories': MenuCategory.objects.filter(is_active=True).count(),
            'total_items': MenuItem.objects.filter(is_available=True).count(),
            'featured_items': MenuItem.objects.filter(is_available=True, is_featured=True).count(),
            'vegan_items': MenuItem.objects.filter(is_available=True, is_vegan=True).count(),
            'gluten_free_items': MenuItem.objects.filter(is_available=True, is_gluten_free=True).count(),
            'total_modifier_groups': ModifierGroup.objects.count(),
            'total_modifiers': Modifier.objects.filter(is_available=True).count(),
            'price_range': {
                'min': MenuItem.objects.filter(is_available=True).aggregate(
                    min_price=models.Min('price')
                )['min_price'] or 0,
                'max': MenuItem.objects.filter(is_available=True).aggregate(
                    max_price=models.Max('price')
                )['max_price'] or 0
            }
        }
        
        return Response(stats)