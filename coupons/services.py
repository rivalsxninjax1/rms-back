from __future__ import annotations

from decimal import Decimal
from typing import Optional, Tuple, Dict, Any
from django.contrib.auth.models import User
from django.db.models import Q, Count, F
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError

from .models import Coupon


class CouponValidationError(Exception):
    """Custom exception for coupon validation errors."""
    pass


def find_active_coupon(code: str) -> Optional[Coupon]:
    """Find an active coupon by code or phrase."""
    if not code:
        return None
    
    code = code.strip().upper()
    
    try:
        coupon = Coupon.objects.get(
            Q(code__iexact=code) | Q(phrase__iexact=code),
            active=True,
        )
        
        if coupon.is_valid_now():
            return coupon
    except Coupon.DoesNotExist:
        pass
    
    return None


def validate_coupon_for_user(coupon: Coupon, user: Optional[User] = None, 
                           order_total: Decimal = Decimal('0.00'),
                           is_first_order: bool = False) -> Tuple[bool, str]:
    """Comprehensive coupon validation for a specific user and order."""
    if not coupon:
        return False, "Coupon not found"
    
    # Basic validity check
    if not coupon.is_valid_now():
        return False, "Coupon is expired or inactive"
    
    # Check minimum order amount
    if coupon.minimum_order_amount and order_total < coupon.minimum_order_amount:
        return False, f"Minimum order amount of ${coupon.minimum_order_amount} required"
    
    # Check customer-specific restrictions
    if user and user.is_authenticated:
        # Get user's previous usage count for this coupon
        from orders.models import Order
        previous_usage = Order.objects.filter(
            user=user,
            applied_coupon_code=coupon.code,
            status__in=['COMPLETED', 'DELIVERED']
        ).count()
        
        can_use, message = coupon.can_be_used_by_customer(
            user=user,
            is_first_order=is_first_order,
            previous_usage_count=previous_usage
        )
        
        if not can_use:
            return False, message
    
    return True, "Valid"


def compute_discount_for_order(coupon: Coupon, order_total: Decimal, 
                             item_count: int = 1, 
                             user: Optional[User] = None,
                             is_first_order: bool = False) -> Tuple[Decimal, Dict[str, Any]]:
    """Compute the discount amount for a given order with detailed breakdown."""
    if not coupon:
        return Decimal('0.00'), {'error': 'No coupon provided'}
    
    # Validate coupon for this user and order
    is_valid, message = validate_coupon_for_user(
        coupon,
        user=user,
        order_total=order_total,
        is_first_order=is_first_order
    )
    
    if not is_valid:
        return Decimal('0.00'), {'error': message}
    
    # Calculate discount using the coupon's method
    discount_amount = coupon.calculate_discount(order_total, item_count)
    
    # Prepare detailed breakdown
    breakdown = {
        'coupon_code': coupon.code,
        'coupon_name': coupon.name,
        'discount_type': coupon.discount_type,
        'original_total': order_total,
        'discount_amount': discount_amount,
        'final_total': max(Decimal('0.00'), order_total - discount_amount),
        'savings_percentage': (
            (discount_amount / order_total * 100).quantize(Decimal('0.01'))
            if order_total > 0 else Decimal('0.00')
        )
    }
    
    # Add type-specific details
    if coupon.discount_type == 'PERCENTAGE':
        breakdown['percentage'] = coupon.percent
        if coupon.maximum_discount_amount:
            breakdown['max_discount'] = coupon.maximum_discount_amount
            breakdown['discount_capped'] = discount_amount >= coupon.maximum_discount_amount
    
    elif coupon.discount_type == 'FIXED_AMOUNT':
        breakdown['fixed_amount'] = coupon.fixed_amount
        breakdown['discount_limited_by_total'] = discount_amount < coupon.fixed_amount
    
    elif coupon.discount_type == 'BUY_X_GET_Y':
        breakdown['buy_quantity'] = coupon.buy_quantity
        breakdown['get_quantity'] = coupon.get_quantity
        if coupon.buy_quantity:
            breakdown['qualifying_sets'] = item_count // coupon.buy_quantity
            breakdown['free_items'] = breakdown['qualifying_sets'] * coupon.get_quantity
    
    return discount_amount, breakdown


def apply_coupon_to_order(coupon: Coupon, order_total: Decimal, 
                         user: Optional[User] = None,
                         item_count: int = 1,
                         is_first_order: bool = False,
                         increment_usage: bool = True) -> Dict[str, Any]:
    """Apply a coupon to an order and return comprehensive results."""
    discount_amount, breakdown = compute_discount_for_order(
        coupon,
        order_total,
        item_count=item_count,
        user=user,
        is_first_order=is_first_order
    )
    
    if 'error' in breakdown:
        return {
            'success': False,
            'error': breakdown['error'],
            'discount_amount': Decimal('0.00')
        }
    
    # Increment usage count if requested
    if increment_usage and discount_amount > 0:
        coupon.increment_usage(discount_amount)
    
    return {
        'success': True,
        'discount_amount': discount_amount,
        'breakdown': breakdown,
        'coupon': {
            'id': coupon.id,
            'code': coupon.code,
            'name': coupon.name,
            'description': coupon.description,
            'discount_type': coupon.discount_type,
            'remaining_uses': (
                coupon.max_uses - coupon.times_used 
                if coupon.max_uses else None
            )
        }
    }


def get_available_coupons_for_user(user: Optional[User] = None, 
                                  order_total: Decimal = Decimal('0.00'),
                                  is_first_order: bool = False) -> list[Dict[str, Any]]:
    """Get all available coupons for a specific user and order context."""
    now = timezone.now()
    
    # Base queryset for active coupons
    coupons = Coupon.objects.filter(
        active=True
    ).filter(
        Q(valid_from__isnull=True) | Q(valid_from__lte=now)
    ).filter(
        Q(valid_to__isnull=True) | Q(valid_to__gt=now)
    ).filter(
        Q(max_uses__isnull=True) | Q(times_used__lt=F('max_uses'))
    )
    
    available_coupons = []
    
    for coupon in coupons:
        is_valid, message = validate_coupon_for_user(
            coupon,
            user=user,
            order_total=order_total,
            is_first_order=is_first_order
        )
        
        if is_valid:
            discount_amount, breakdown = compute_discount_for_order(
                coupon,
                order_total,
                item_count=1,
                user=user,
                is_first_order=is_first_order
            )
            
            if discount_amount > 0:
                available_coupons.append({
                    'id': coupon.id,
                    'code': coupon.code,
                    'name': coupon.name,
                    'description': coupon.description,
                    'discount_type': coupon.discount_type,
                    'potential_discount': discount_amount,
                    'savings_percentage': breakdown.get('savings_percentage', Decimal('0.00')),
                    'minimum_order_amount': coupon.minimum_order_amount,
                    'valid_to': coupon.valid_to,
                    'remaining_uses': (
                        coupon.max_uses - coupon.times_used 
                        if coupon.max_uses else None
                    )
                })
    
    # Sort by potential discount amount (highest first)
    available_coupons.sort(key=lambda x: x['potential_discount'], reverse=True)
    
    return available_coupons


def find_best_coupon_for_order(user: Optional[User] = None,
                              order_total: Decimal = Decimal('0.00'),
                              is_first_order: bool = False) -> Optional[Dict[str, Any]]:
    """Find the best available coupon for a given order."""
    available_coupons = get_available_coupons_for_user(
        user=user,
        order_total=order_total,
        is_first_order=is_first_order
    )
    
    if available_coupons:
        return available_coupons[0]  # Already sorted by discount amount
    
    return None


def bulk_validate_coupons(coupon_codes: list[str], 
                         user: Optional[User] = None,
                         order_total: Decimal = Decimal('0.00'),
                         is_first_order: bool = False) -> Dict[str, Dict[str, Any]]:
    """Validate multiple coupons at once."""
    results = {}
    
    for code in coupon_codes:
        coupon = find_active_coupon(code)
        if coupon:
            is_valid, message = validate_coupon_for_user(
                coupon,
                user=user,
                order_total=order_total,
                is_first_order=is_first_order
            )
            
            if is_valid:
                discount_amount, breakdown = compute_discount_for_order(
                    coupon,
                    order_total,
                    item_count=1,
                    user=user,
                    is_first_order=is_first_order
                )
                
                results[code] = {
                    'valid': True,
                    'coupon_id': coupon.id,
                    'discount_amount': discount_amount,
                    'breakdown': breakdown
                }
            else:
                results[code] = {
                    'valid': False,
                    'error': message
                }
        else:
            results[code] = {
                'valid': False,
                'error': 'Coupon not found or inactive'
            }
    
    return results
