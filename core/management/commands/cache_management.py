from django.core.management.base import BaseCommand, CommandError
from django.core.cache import cache
from django.conf import settings
from core.cache_service import CacheService
from core.cache_decorators import invalidate_cache_pattern
import time


class Command(BaseCommand):
    help = 'Manage application cache - warm up, clear, or get statistics'

    def add_arguments(self, parser):
        parser.add_argument(
            'action',
            choices=['warmup', 'clear', 'stats', 'clear-pattern'],
            help='Action to perform on cache'
        )
        
        parser.add_argument(
            '--pattern',
            type=str,
            help='Cache key pattern to clear (for clear-pattern action)'
        )
        
        parser.add_argument(
            '--organization-id',
            type=int,
            default=1,
            help='Organization ID for cache operations'
        )
        
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output'
        )

    def handle(self, *args, **options):
        action = options['action']
        verbose = options['verbose']
        organization_id = options['organization_id']
        
        if action == 'warmup':
            self.warmup_cache(organization_id, verbose)
        elif action == 'clear':
            self.clear_cache(verbose)
        elif action == 'stats':
            self.show_stats(verbose)
        elif action == 'clear-pattern':
            pattern = options.get('pattern')
            if not pattern:
                raise CommandError('--pattern is required for clear-pattern action')
            self.clear_pattern(pattern, verbose)

    def warmup_cache(self, organization_id, verbose=False):
        """Warm up cache with commonly accessed data."""
        self.stdout.write(self.style.SUCCESS('Starting cache warmup...'))
        start_time = time.time()
        
        try:
            # Warm up menu items
            if verbose:
                self.stdout.write('Warming up menu items...')
            
            from menu.models import MenuItem, MenuCategory
            
            # Cache menu items
            menu_items = list(MenuItem.objects.filter(
                is_available=True
            ).select_related('category').order_by('category__name', 'name').values(
                'id', 'name', 'description', 'price', 'image', 
                'category__name', 'category_id', 'is_vegetarian', 'preparation_time'
            ))
            
            CacheService.set_menu_items(organization_id, menu_items)
            
            # Cache menu categories
            categories = list(MenuCategory.objects.filter(
                items__is_available=True
            ).distinct().order_by('name').values('id', 'name', 'description'))
            
            cache.set(
                f"menu_categories:{organization_id}", 
                categories, 
                3600
            )
            
            # Cache individual menu items
            for item in menu_items[:20]:  # Cache top 20 items
                item_id = item['id']
                cache.set(
                    f"menu_item:{item_id}", 
                    item, 
                    3600
                )
            
            self.stdout.write(f"✓ Cached {len(menu_items)} menu items and {len(categories)} categories")
            
            # Warm up popular items
            if verbose:
                self.stdout.write('Warming up popular items...')
            
            from orders.cache_utils import get_popular_items_cached
            get_popular_items_cached(organization_id, 10)
            
            # Warm up tables data
            if verbose:
                self.stdout.write('Warming up tables data...')
            
            # Import and warm up tables
            try:
                from storefront.api import api_tables
                from django.http import HttpRequest
                
                # Create a mock request for warming up
                mock_request = HttpRequest()
                mock_request.method = 'GET'
                
                # This will populate the cache
                api_tables(mock_request)
            except Exception as e:
                if verbose:
                    self.stdout.write(f'Warning: Could not warm up tables data: {e}')
            
            # Warm up analytics data
            if verbose:
                self.stdout.write('Warming up analytics data...')
            
            # Cache some basic analytics data
            cache.set(
                f'analytics_daily_stats:{organization_id}',
                {'revenue': 0, 'orders': 0, 'customers': 0},
                timeout=3600
            )
            
            elapsed = time.time() - start_time
            self.stdout.write(
                self.style.SUCCESS(
                    f'Cache warmup completed in {elapsed:.2f} seconds'
                )
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Cache warmup failed: {str(e)}')
            )
            raise CommandError(f'Cache warmup failed: {str(e)}')

    def clear_cache(self, verbose=False):
        """Clear all cache."""
        self.stdout.write(self.style.WARNING('Clearing all cache...'))
        
        try:
            CacheService.clear_all_cache()
            self.stdout.write(self.style.SUCCESS('All cache cleared successfully'))
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Failed to clear cache: {str(e)}')
            )
            raise CommandError(f'Failed to clear cache: {str(e)}')

    def clear_pattern(self, pattern, verbose=False):
        """Clear cache by pattern."""
        self.stdout.write(
            self.style.WARNING(f'Clearing cache pattern: {pattern}')
        )
        
        try:
            count = CacheService.delete_pattern(pattern)
            self.stdout.write(
                self.style.SUCCESS(
                    f'Cleared {count} cache keys matching pattern: {pattern}'
                )
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Failed to clear pattern: {str(e)}')
            )
            raise CommandError(f'Failed to clear pattern: {str(e)}')

    def show_stats(self, verbose=False):
        """Show cache statistics."""
        self.stdout.write(self.style.SUCCESS('Cache Statistics:'))
        
        try:
            stats = CacheService.get_cache_stats()
            
            self.stdout.write(f"Backend: {stats.get('backend', 'Unknown')}")
            self.stdout.write(f"Total Keys: {stats.get('total_keys', 'N/A')}")
            self.stdout.write(f"Memory Usage: {stats.get('memory_usage', 'N/A')}")
            self.stdout.write(f"Hit Rate: {stats.get('hit_rate', 'N/A')}%")
            
            if verbose and 'recent_keys' in stats:
                self.stdout.write('\nRecent Cache Keys:')
                for key in stats['recent_keys'][:10]:  # Show first 10
                    self.stdout.write(f"  - {key}")
                    
            # Test cache connectivity
            test_key = 'cache_test_key'
            test_value = 'cache_test_value'
            
            cache.set(test_key, test_value, 60)
            retrieved_value = cache.get(test_key)
            
            if retrieved_value == test_value:
                self.stdout.write(
                    self.style.SUCCESS('✓ Cache connectivity test passed')
                )
                cache.delete(test_key)
            else:
                self.stdout.write(
                    self.style.ERROR('✗ Cache connectivity test failed')
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Failed to get cache stats: {str(e)}')
            )
            raise CommandError(f'Failed to get cache stats: {str(e)}')