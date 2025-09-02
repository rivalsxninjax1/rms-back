from typing import Dict, List, Any, Tuple
from decimal import Decimal, InvalidOperation
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
import json
import logging
from django.utils import timezone
from django.core.exceptions import ValidationError

from .views import _cart_set, _enrich, _normalize_items
from .cache_utils import get_menu_items_batch_cached
from .session_utils import get_session_cart_manager

logger = logging.getLogger(__name__)

# Constants for validation
MAX_CART_ITEMS = 50
MAX_ITEM_QUANTITY = 99
MAX_REQUEST_SIZE = 1024 * 1024  # 1MB


def _validate_request_size(request) -> bool:
    """Validate request size to prevent abuse."""
    content_length = request.META.get('CONTENT_LENGTH')
    if content_length and int(content_length) > MAX_REQUEST_SIZE:
        return False
    return True


def _validate_cart_items(items: List[Dict[str, Any]]) -> Tuple[bool, str]:
    """Validate cart items structure and constraints."""
    if not isinstance(items, list):
        return False, "Items must be a list"
    
    if len(items) > MAX_CART_ITEMS:
        return False, f"Too many items. Maximum {MAX_CART_ITEMS} allowed"
    
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            return False, f"Item {i} must be an object"
        
        # Validate required fields
        if 'id' not in item:
            return False, f"Item {i} missing required 'id' field"
        
        try:
            item_id = int(item['id'])
            if item_id <= 0:
                return False, f"Item {i} has invalid id: {item_id}"
        except (ValueError, TypeError):
            return False, f"Item {i} has non-numeric id"
        
        # Validate quantity
        quantity = item.get('quantity', 1)
        try:
            quantity = int(quantity)
            if quantity <= 0 or quantity > MAX_ITEM_QUANTITY:
                return False, f"Item {i} has invalid quantity: {quantity}"
        except (ValueError, TypeError):
            return False, f"Item {i} has non-numeric quantity"
        
        # Validate modifiers if present
        modifiers = item.get('modifiers', [])
        if modifiers and not isinstance(modifiers, list):
            return False, f"Item {i} modifiers must be a list"
        
        for j, modifier in enumerate(modifiers):
            if not isinstance(modifier, dict) or 'id' not in modifier:
                return False, f"Item {i} modifier {j} is invalid"
    
    return True, ""


def _validate_cart_meta(meta: Dict[str, Any]) -> Tuple[bool, str]:
    """Validate cart metadata."""
    if not isinstance(meta, dict):
        return False, "Meta must be an object"
    
    # Validate tip amount if present
    if 'tip_amount' in meta:
        try:
            tip = Decimal(str(meta['tip_amount']))
            if tip < 0 or tip > Decimal('999.99'):
                return False, "Invalid tip amount"
        except (InvalidOperation, ValueError):
            return False, "Tip amount must be a valid decimal"
    
    # Validate discount if present
    if 'discount_cents' in meta:
        try:
            discount = int(meta['discount_cents'])
            if discount < 0 or discount > 99999:  # $999.99 max
                return False, "Invalid discount amount"
        except (ValueError, TypeError):
            return False, "Discount must be a valid integer"
    
    return True, ""


@csrf_exempt
@require_http_methods(["POST"])
def bulk_cart_sync(request):
    """
    Optimized bulk cart synchronization endpoint with comprehensive validation.
    Accepts the entire cart state and updates the session in one operation.
    """
    start_time = timezone.now()
    
    try:
        # Validate request size
        if not _validate_request_size(request):
            logger.warning(f"Request size too large from {request.META.get('REMOTE_ADDR')}")
            return JsonResponse({
                'success': False,
                'error': 'Request too large',
                'code': 'REQUEST_TOO_LARGE'
            }, status=413)
        
        # Use the session cart manager
        cart_manager = get_session_cart_manager(request)
        
        # Ensure session exists
        if not cart_manager.ensure_session_exists():
            logger.error("Session initialization failed")
            return JsonResponse({
                'success': False,
                'error': 'Session initialization failed',
                'code': 'SESSION_INIT_FAILED'
            }, status=500)
        
        # Parse and validate request data
        if not request.body:
            # Empty body means clear cart
            cart_items = []
            data = {}
            logger.debug("Empty request body - clearing cart")
        else:
            try:
                data = json.loads(request.body)
                if not isinstance(data, dict):
                    return JsonResponse({
                        'success': False,
                        'error': 'Request data must be an object',
                        'code': 'INVALID_DATA_FORMAT'
                    }, status=400)
                
                cart_items = data.get('items', [])
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON in cart sync: {e}")
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid JSON data',
                    'code': 'INVALID_JSON',
                    'details': str(e)
                }, status=400)
        
        # Validate cart items
        items_valid, items_error = _validate_cart_items(cart_items)
        if not items_valid:
            logger.warning(f"Cart items validation failed: {items_error}")
            return JsonResponse({
                'success': False,
                'error': items_error,
                'code': 'INVALID_ITEMS'
            }, status=400)
        
        # Validate cart metadata
        meta = data.get('meta', {})
        meta_valid, meta_error = _validate_cart_meta(meta)
        if not meta_valid:
            logger.warning(f"Cart meta validation failed: {meta_error}")
            return JsonResponse({
                'success': False,
                'error': meta_error,
                'code': 'INVALID_META'
            }, status=400)
        
        # Normalize and validate items
        try:
            normalized_items = _normalize_items(cart_items)
        except Exception as e:
            logger.error(f"Item normalization failed: {e}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to normalize cart items',
                'code': 'NORMALIZATION_FAILED',
                'details': str(e)
            }, status=400)
        
        # Update session cart using the session manager
        try:
            success = cart_manager.set_cart_data(normalized_items, meta)
            if not success:
                logger.error("Failed to update cart data in session")
                return JsonResponse({
                    'success': False,
                    'error': 'Failed to update cart data',
                    'code': 'CART_UPDATE_FAILED'
                }, status=500)
        except Exception as e:
            logger.error(f"Cart data update exception: {e}")
            return JsonResponse({
                'success': False,
                'error': 'Cart update failed',
                'code': 'CART_UPDATE_EXCEPTION',
                'details': str(e)
            }, status=500)
        
        # Return enriched cart data
        try:
            enriched_items, subtotal = _enrich(normalized_items)
            logger.debug(f"Enriched {len(enriched_items)} items, subtotal: {subtotal}")
        except Exception as e:
            logger.error(f"Cart enrichment failed: {e}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to enrich cart data',
                'code': 'ENRICHMENT_FAILED',
                'details': str(e)
            }, status=500)
        
        # Get cart metadata with error handling
        try:
            from .views import _cart_meta_get
            cart_meta = _cart_meta_get(request)
            tip_amount = Decimal(str(cart_meta.get('tip_amount', '0.00')))
            
            # Validate tip amount
            if tip_amount < 0:
                tip_amount = Decimal('0.00')
                logger.warning("Negative tip amount detected, reset to 0")
            
            grand_total = subtotal + tip_amount
            
        except Exception as e:
            logger.error(f"Metadata retrieval failed: {e}")
            # Use fallback values
            tip_amount = Decimal('0.00')
            grand_total = subtotal
            cart_meta = {}
        
        # Update last activity timestamp
        try:
            request.session['cart_last_activity'] = timezone.now().isoformat()
            request.session.modified = True
            request.session.save()
        except Exception as e:
            logger.warning(f"Failed to update session timestamp: {e}")
            # Don't fail the entire request for timestamp update failure
        
        # Calculate processing time
        processing_time = (timezone.now() - start_time).total_seconds() * 1000
        
        # Log successful sync
        logger.info(f"Cart sync successful: {len(enriched_items)} items, "
                   f"subtotal: {subtotal}, processing: {processing_time:.2f}ms")
        
        return JsonResponse({
            'success': True,
            'items': enriched_items,
            'subtotal': str(subtotal),
            'tip_amount': str(tip_amount),
            'grand_total': str(grand_total),
            'currency': 'NPR',  # Updated to match restaurant currency
            'item_count': len(enriched_items),
            'total_quantity': sum(int(item.get('quantity', 1)) for item in enriched_items),
            'timestamp': timezone.now().isoformat(),
            'processing_time_ms': round(processing_time, 2)
        })
        
    except Exception as e:
        # Catch-all error handler
        import traceback
        error_id = timezone.now().strftime('%Y%m%d_%H%M%S')
        logger.error(f"Unexpected error in cart sync [{error_id}]: {e}\n{traceback.format_exc()}")
        
        return JsonResponse({
            'success': False,
            'error': 'An unexpected error occurred',
            'code': 'UNEXPECTED_ERROR',
            'error_id': error_id,
            'details': str(e) if logger.isEnabledFor(logging.DEBUG) else None
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def cart_status(request):
    """
    Lightweight endpoint to get cart status without full enrichment.
    Returns basic cart info for badge updates with comprehensive error handling.
    """
    start_time = timezone.now()
    
    try:
        # Use session cart manager for consistent session handling
        cart_manager = get_session_cart_manager(request)
        
        # Ensure session exists (but don't fail if it doesn't for status check)
        if not cart_manager.ensure_session_exists():
            logger.debug("No session available for cart status check")
            return JsonResponse({
                'success': True,
                'total_items': 0,
                'item_count': 0,
                'has_items': False,
                'session_available': False
            })
        
        # Get cart items with error handling
        try:
            from .views import _cart_get
            items = _cart_get(request)
            
            # Validate items structure
            if not isinstance(items, list):
                logger.warning(f"Cart items is not a list: {type(items)}")
                items = []
                
        except Exception as e:
            logger.error(f"Failed to get cart items for status: {e}")
            items = []
        
        # Calculate totals with validation
        total_items = 0
        item_count = len(items)
        
        for item in items:
            if isinstance(item, dict):
                try:
                    quantity = int(item.get('quantity', 1))
                    if quantity > 0:  # Only count positive quantities
                        total_items += quantity
                except (ValueError, TypeError):
                    logger.warning(f"Invalid quantity in cart item: {item.get('quantity')}")
                    total_items += 1  # Default to 1 for invalid quantities
        
        # Calculate processing time
        processing_time = (timezone.now() - start_time).total_seconds() * 1000
        
        # Log status check (debug level to avoid spam)
        logger.debug(f"Cart status check: {item_count} items, {total_items} total, "
                    f"processing: {processing_time:.2f}ms")
        
        return JsonResponse({
            'success': True,
            'total_items': total_items,
            'item_count': item_count,
            'has_items': item_count > 0,
            'session_available': True,
            'timestamp': timezone.now().isoformat(),
            'processing_time_ms': round(processing_time, 2)
        })
        
    except Exception as e:
        # Comprehensive error handling for status endpoint
        import traceback
        error_id = timezone.now().strftime('%Y%m%d_%H%M%S')
        logger.error(f"Unexpected error in cart status [{error_id}]: {e}\n{traceback.format_exc()}")
        
        return JsonResponse({
            'success': False,
            'error': 'Failed to get cart status',
            'code': 'STATUS_CHECK_FAILED',
            'error_id': error_id,
            'details': str(e) if logger.isEnabledFor(logging.DEBUG) else None
        }, status=500)