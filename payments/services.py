# FILE: payments/services.py
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Tuple, List, Dict, Any

from io import BytesIO

import stripe
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from django.db import transaction

from billing.models import Payment
from .models import StripePaymentIntent, StripeWebhookEvent, PaymentRefund
from orders.models import Order, Cart
from engagement.models import OrderExtras
from engagement.services import (
    get_pending_tip_for_user,
    best_loyalty_discount_for_user,
    choose_better_discount,
    clear_pending_tips_for_user,
)

# Configure logging
logger = logging.getLogger(__name__)
stripe.api_key = getattr(settings, "STRIPE_SECRET_KEY", "")


# ---------------------------
# Money / URL helpers
# ---------------------------
def _currency() -> str:
    # keep API compatible with your existing codebase
    return getattr(settings, "CURRENCY", getattr(settings, "STRIPE_CURRENCY", "usd")).lower()


def _money_cents(amount: Decimal) -> int:
    q = Decimal(amount or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return int((q * 100).to_integral_value())


def _success_url(order: Order) -> str:
    return getattr(settings, "SITE_URL", "").rstrip("/") + reverse("payments:checkout-success")


def _cancel_url(order: Order) -> str:
    return getattr(settings, "SITE_URL", "").rstrip("/") + reverse("payments:checkout-cancel")


# ---------------------------
# Order extras (uses engagement.OrderExtras rows)
# ---------------------------
def _get_extra_amount(order: Order, name: str) -> Decimal:
    """
    Fetch a single extra by name (e.g., 'tip', 'coupon_discount', 'loyalty_discount').
    Returns Decimal('0.00') if not found.
    """
    try:
        row = OrderExtras.objects.filter(order=order, name=name).order_by("-id").first()
        return Decimal(str(row.amount)) if row else Decimal("0.00")
    except Exception:
        logger.exception("Failed to read OrderExtras '%s' for order %s", name, getattr(order, "id", None))
        return Decimal("0.00")


def _set_extra_amount(order: Order, name: str, amount: Decimal) -> None:
    """
    Upsert a single extra by name.
    """
    try:
        obj, _ = OrderExtras.objects.get_or_create(order=order, name=name, defaults={"amount": Decimal("0.00")})
        if Decimal(str(obj.amount)) != Decimal(str(amount)):
            obj.amount = Decimal(str(amount)).quantize(Decimal("0.01"))
            obj.save(update_fields=["amount"])
    except Exception:
        logger.exception("Failed to save OrderExtras '%s' for order %s", name, getattr(order, "id", None))


# ---------------------------
# Totals
# ---------------------------
def compute_order_total(order: Order) -> Tuple[Decimal, Decimal]:
    """
    Returns (subtotal, tax) for the order items only (no tips/discounts).
    Implementations may vary; keep API stable.
    """
    subtotal = Decimal("0.00")
    for it in order.items.all():
        unit = Decimal(str(getattr(it, "unit_price", 0) or 0))
        qty = int(getattr(it, "quantity", 0) or 0)
        subtotal += (unit * qty)
    subtotal = subtotal.quantize(Decimal("0.01"))
    tax_rate = Decimal(str(getattr(settings, "SALES_TAX_RATE", 0) or 0))  # e.g. 0.075
    tax = (subtotal * tax_rate).quantize(Decimal("0.01"))
    return subtotal, tax


def _build_line_items(order: Order, tip_amount: Decimal) -> List[Dict[str, Any]]:
    """
    Build Stripe Checkout line_items:
    - One "Order #<id>" items line (subtotal+tax)
    - "Tip" as a separate positive line item if > 0
    Loyalty/coupon discount is passed via Checkout 'discounts' because Stripe does NOT allow negative unit_amount.
    """
    subtotal, tax = compute_order_total(order)
    lines: List[Dict[str, Any]] = [{
        "price_data": {
            "currency": _currency(),
            "product_data": {"name": f"Order #{order.id}"},
            "unit_amount": _money_cents(subtotal + tax),
        },
        "quantity": 1,
    }]
    if tip_amount and Decimal(tip_amount) > 0:
        lines.append({
            "price_data": {
                "currency": _currency(),
                "product_data": {"name": "Tip"},
                "unit_amount": _money_cents(Decimal(tip_amount)),
            },
            "quantity": 1,
        })
    return lines


def _apply_best_discount(order: Order, loyalty_amount: Decimal, coupon_amount: Decimal) -> Tuple[Dict[str, Any], Decimal, str]:
    """
    Create a one-off Stripe Coupon for amount_off = chosen discount (if any)
    and return (discounts_param, chosen_amount, source_label) for Checkout Session.
    """
    amount, source = choose_better_discount(loyalty_amount, coupon_amount)
    if amount <= 0:
        return {}, Decimal("0.00"), "none"

    # Create or reuse a short-lived coupon
    try:
        coupon = stripe.Coupon.create(
            amount_off=_money_cents(amount),
            currency=_currency(),
            duration="once",
            name=f"{source.title()} discount",
        )
        return {"discounts": [{"coupon": coupon["id"]}]}, amount, source
    except Exception:
        logger.exception("Failed to create Stripe coupon; proceeding without discount")
        return {}, Decimal("0.00"), "none"


# ---------------------------
# Stripe Checkout
# ---------------------------
def checkout_session_from_order(order: Order):
    """
    Alias for create_checkout_session for backward compatibility.
    """
    return create_checkout_session(order)


def create_checkout_session(order: Order):
    """
    Builds a Stripe Checkout Session with items + tip + best discount (loyalty vs coupon).
    Stores resolved numbers as OrderExtras rows so invoices/receipts show correct lines.
    """
    success_url = _success_url(order)
    cancel_url = _cancel_url(order)

    # Resolve tip from PendingTip or existing extras
    user = getattr(order, "user", None) or getattr(order, "created_by", None)
    tip_amount = _get_extra_amount(order, "tip")
    if tip_amount <= 0:
        # fall back to pending tip recorder
        pending = get_pending_tip_for_user(user)
        if pending > 0:
            tip_amount = pending
            _set_extra_amount(order, "tip", tip_amount)

    # Loyalty vs Coupon (exclude tips from base)
    subtotal, tax = compute_order_total(order)
    loyalty_amount, loyalty_msg = best_loyalty_discount_for_user(user, subtotal=subtotal + tax)
    coupon_amount = _get_extra_amount(order, "coupon_discount")  # if your flow saves coupon elsewhere, adapt here

    discounts_param, chosen_amount, chosen_source = _apply_best_discount(order, loyalty_amount, coupon_amount)
    if chosen_source == "loyalty" and loyalty_msg:
        _set_extra_amount(order, "loyalty_discount", chosen_amount)
    elif chosen_source == "coupon":
        _set_extra_amount(order, "coupon_discount", chosen_amount)

    # Build line items (tip shown as its own line)
    line_items = _build_line_items(order, tip_amount)

    # Create the session
    session = stripe.checkout.Session.create(
        mode="payment",
        payment_method_types=["card"],
        line_items=line_items,
        metadata={"order_id": str(order.id)},
        client_reference_id=str(order.id),
        success_url=success_url,
        cancel_url=cancel_url,
        **(discounts_param or {}),
    )

    # Update Payment record if present (tolerate schema differences)
    try:
        pay, _ = Payment.objects.get_or_create(order=order)
        # Dynamically set available fields only
        update_fields = []
        if hasattr(pay, "stripe_session_id"):
            setattr(pay, "stripe_session_id", session.get("id"))
            update_fields.append("stripe_session_id")
        if hasattr(pay, "stripe_checkout_url"):
            setattr(pay, "stripe_checkout_url", session.get("url"))
            update_fields.append("stripe_checkout_url")
        if hasattr(pay, "currency"):
            setattr(pay, "currency", _currency())
            update_fields.append("currency")
        if hasattr(pay, "amount"):
            try:
                amt = getattr(order, "total_amount", None) or getattr(order, "total", None)
                if amt is not None:
                    setattr(pay, "amount", amt)
                    update_fields.append("amount")
            except Exception:
                pass
        if update_fields:
            pay.save(update_fields=update_fields)
    except Exception:
        logger.exception("Failed to link Payment to Stripe Session for order %s", order.id)

    # Persist final numbers for invoice/receipt lines (excluding tips from base)
    try:
        final_total = (subtotal + tax - (chosen_amount or Decimal("0.00"))).quantize(Decimal("0.01"))
        _set_extra_amount(order, "final_total_excl_tip", final_total)
    except Exception:
        logger.exception("Failed to save final totals for order %s", order.id)

    return session


# ---------------------------
# Enhanced Invoice & Receipt Generation
# ---------------------------
def generate_order_invoice_pdf(order: Order) -> tuple[str, bytes] | tuple[None, None]:
    """
    Create a comprehensive invoice PDF with professional styling and complete order details.
    Includes company branding, itemized breakdown, taxes, discounts, and payment information.
    """
    try:
        from reportlab.lib.pagesizes import A4, letter
        from reportlab.lib.units import inch
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.pdfgen import canvas
    except Exception:
        logger.warning("reportlab not installed; skipping invoice PDF generation")
        return None, None

    # Calculate totals
    subtotal, tax = compute_order_total(order)
    tip = _get_extra_amount(order, "tip")
    loyalty = _get_extra_amount(order, "loyalty_discount")
    coupon = _get_extra_amount(order, "coupon_discount")
    final_total = _get_extra_amount(order, "final_total_excl_tip") or (subtotal + tax)
    grand_total = (final_total + tip).quantize(Decimal('0.01'))

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
    
    # Container for the 'Flowable' objects
    elements = []
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.darkblue
    )
    
    header_style = ParagraphStyle(
        'CustomHeader',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=12,
        textColor=colors.darkblue
    )
    
    # Company Header
    company_name = getattr(settings, 'COMPANY_NAME', 'Restaurant Management System')
    company_address = getattr(settings, 'COMPANY_ADDRESS', '123 Main St, City, State 12345')
    company_phone = getattr(settings, 'COMPANY_PHONE', '(555) 123-4567')
    company_email = getattr(settings, 'COMPANY_EMAIL', 'info@restaurant.com')
    
    elements.append(Paragraph(company_name, title_style))
    elements.append(Paragraph(f"{company_address}<br/>{company_phone} | {company_email}", styles['Normal']))
    elements.append(Spacer(1, 20))
    
    # Invoice Header
    elements.append(Paragraph("INVOICE", header_style))
    
    # Order Information Table
    order_info_data = [
        ['Invoice #:', f'INV-{order.id:06d}'],
        ['Order #:', f'{order.id}'],
        ['Date:', order.created_at.strftime('%B %d, %Y')],
        ['Time:', order.created_at.strftime('%I:%M %p')],
        ['Status:', order.status.replace('_', ' ').title()],
    ]
    
    if hasattr(order, 'user') and order.user:
        order_info_data.extend([
            ['Customer:', f'{order.user.get_full_name() or order.user.username}'],
            ['Email:', order.user.email or 'N/A'],
        ])
    
    order_info_table = Table(order_info_data, colWidths=[1.5*inch, 3*inch])
    order_info_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    
    elements.append(order_info_table)
    elements.append(Spacer(1, 20))
    
    # Items Table
    elements.append(Paragraph("Order Items", header_style))
    
    items_data = [['Item', 'Qty', 'Unit Price', 'Total']]
    
    for item in order.items.all():
        item_name = getattr(item, 'name', 'Unknown Item')
        quantity = getattr(item, 'quantity', 1)
        unit_price = Decimal(str(getattr(item, 'unit_price', 0) or 0))
        line_total = unit_price * quantity
        
        items_data.append([
            item_name,
            str(quantity),
            f'${unit_price:.2f}',
            f'${line_total:.2f}'
        ])
    
    items_table = Table(items_data, colWidths=[3*inch, 0.75*inch, 1*inch, 1*inch])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (0, 1), (0, -1), 'LEFT'),  # Item names left-aligned
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    
    elements.append(items_table)
    elements.append(Spacer(1, 20))
    
    # Totals Table
    totals_data = [
        ['Subtotal:', f'${subtotal:.2f}'],
        ['Tax:', f'${tax:.2f}'],
    ]
    
    if coupon > 0:
        totals_data.append(['Coupon Discount:', f'-${coupon:.2f}'])
    if loyalty > 0:
        totals_data.append(['Loyalty Discount:', f'-${loyalty:.2f}'])
    if tip > 0:
        totals_data.append(['Tip:', f'${tip:.2f}'])
    
    totals_data.append(['', ''])  # Separator line
    totals_data.append(['TOTAL:', f'${grand_total:.2f}'])
    
    totals_table = Table(totals_data, colWidths=[3*inch, 1.5*inch])
    totals_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 12),
        ('LINEBELOW', (0, -2), (-1, -2), 1, colors.black),
        ('FONTSIZE', (0, 0), (-1, -3), 10),
    ]))
    
    elements.append(totals_table)
    elements.append(Spacer(1, 30))
    
    # Payment Information
    if hasattr(order, 'payment_method') and order.payment_method:
        elements.append(Paragraph("Payment Information", header_style))
        payment_info = f"Payment Method: {order.payment_method.replace('_', ' ').title()}"
        if hasattr(order, 'payment_reference') and order.payment_reference:
            payment_info += f"<br/>Reference: {order.payment_reference}"
        elements.append(Paragraph(payment_info, styles['Normal']))
        elements.append(Spacer(1, 20))
    
    # Footer
    footer_text = "Thank you for your business!<br/>" + \
                 "For questions about this invoice, please contact us at " + \
                 f"{company_phone} or {company_email}"
    elements.append(Paragraph(footer_text, styles['Normal']))
    
    # Build PDF
    doc.build(elements)
    
    filename = f"invoice_order_{order.id}.pdf"
    return filename, buf.getvalue()


def generate_receipt_pdf(order: Order, payment_intent: StripePaymentIntent = None) -> tuple[str, bytes] | tuple[None, None]:
    """
    Generate a customer receipt PDF with payment confirmation details.
    Optimized for thermal printer compatibility and customer records.
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import inch
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    except Exception:
        logger.warning("reportlab not installed; skipping receipt PDF generation")
        return None, None

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=(4*inch, 11*inch), rightMargin=0.25*inch, 
                          leftMargin=0.25*inch, topMargin=0.25*inch, bottomMargin=0.25*inch)
    
    elements = []
    styles = getSampleStyleSheet()
    
    # Receipt-specific styles
    receipt_title = ParagraphStyle(
        'ReceiptTitle',
        parent=styles['Heading1'],
        fontSize=16,
        alignment=TA_CENTER,
        spaceAfter=10
    )
    
    receipt_normal = ParagraphStyle(
        'ReceiptNormal',
        parent=styles['Normal'],
        fontSize=9,
        alignment=TA_CENTER
    )
    
    # Header
    company_name = getattr(settings, 'COMPANY_NAME', 'Restaurant')
    elements.append(Paragraph(company_name, receipt_title))
    elements.append(Paragraph("CUSTOMER RECEIPT", receipt_normal))
    elements.append(Spacer(1, 10))
    
    # Transaction details
    elements.append(Paragraph(f"Order #: {order.id}", receipt_normal))
    elements.append(Paragraph(f"Date: {order.created_at.strftime('%m/%d/%Y %I:%M %p')}", receipt_normal))
    
    if payment_intent:
        elements.append(Paragraph(f"Payment ID: {payment_intent.stripe_payment_intent_id[-8:]}", receipt_normal))
        elements.append(Paragraph(f"Amount: ${payment_intent.amount_dollars:.2f}", receipt_normal))
        elements.append(Paragraph(f"Status: {payment_intent.status.replace('_', ' ').title()}", receipt_normal))
    
    elements.append(Spacer(1, 15))
    elements.append(Paragraph("Thank you for your order!", receipt_normal))
    
    doc.build(elements)
    
    filename = f"receipt_order_{order.id}.pdf"
    return filename, buf.getvalue()


def save_invoice_pdf_file(order: Order) -> Optional[str]:
    try:
        filename, pdf_bytes = generate_order_invoice_pdf(order)
        if not filename or not pdf_bytes:
            return None
        if hasattr(order, "invoice_pdf"):
            from django.core.files.base import ContentFile
            if not order.invoice_pdf:
                order.invoice_pdf.save(filename, ContentFile(pdf_bytes), save=True)
        return filename
    except Exception as e:
        logger.exception("Failed to save invoice PDF: %s", e)
        return None


# ---------------------------
# Payment finalization hook (needed by payments/views.py)
# ---------------------------
def mark_paid(order: Order, stripe_event: Optional[dict[str, Any]] = None) -> None:
    """
    Finalize order after Stripe confirms payment (webhook or success handler).
    - Mark as PAID / is_paid
    - Set paid_at
    - Clear user's pending tips
    - Do not modify other features (invoices, coupons, RMS admin, etc.)
    """
    if not order:
        return
    if getattr(order, "is_paid", False):
        # idempotent
        return

    with transaction.atomic():
        # Mark paid
        if hasattr(order, "is_paid"):
            order.is_paid = True
        if hasattr(order, "status"):
            order.status = "PAID"
        if hasattr(order, "paid_at"):
            order.paid_at = timezone.now()
        order.save(update_fields=[f for f in ["is_paid", "status", "paid_at"] if hasattr(order, f)])

        # Clear pending tips for this user
        user = getattr(order, "user", None) or getattr(order, "created_by", None)
        try:
            clear_pending_tips_for_user(user)
        except Exception:
            logger.exception("Failed to clear pending tips for user after payment (order %s)", order.id)

        # Optionally persist a final invoice PDF
        try:
            save_invoice_pdf_file(order)
        except Exception:
            logger.exception("Failed to save invoice for order %s", order.id)


def mark_order_as_paid(order: Order) -> None:
    """Mark an order as paid and update related models."""
    order.paid_at = timezone.now()
    order.save(update_fields=["paid_at"])
    
    # Create payment record in billing
    Payment.objects.create(
        order=order,
        amount=order.total,
        currency=order.currency or "USD",
        status="completed",
        reference=f"stripe_{order.stripe_payment_intent or 'manual'}"
    )


class StripePaymentService:
    """
    Comprehensive Stripe payment service with webhook handling and idempotency.
    """
    
    def __init__(self):
        self.stripe_secret_key = getattr(settings, 'STRIPE_SECRET_KEY', '')
        self.stripe_webhook_secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', '')
        stripe.api_key = self.stripe_secret_key
    
    @staticmethod
    def create_payment_intent(order: Order, return_url: str = None, payment_method_types: list = None) -> StripePaymentIntent:
        """
        Create a Stripe PaymentIntent for the given order with enhanced options.
        """
        amount_cents = int(order.total * 100)
        
        # Default payment method types
        if not payment_method_types:
            payment_method_types = ['card', 'apple_pay', 'google_pay']
        
        try:
            # Enhanced metadata with more order details
            metadata = {
                'order_id': str(order.id),
                'order_total': str(order.total),
                'order_status': order.status,
                'created_at': order.created_at.isoformat(),
            }
            
            # Add customer information if available
            if hasattr(order, 'user') and order.user:
                metadata.update({
                    'customer_id': str(order.user.id),
                    'customer_email': order.user.email or '',
                    'customer_name': order.user.get_full_name() or order.user.username,
                })
            
            # Add delivery information if available
            if hasattr(order, 'delivery_address') and order.delivery_address:
                metadata['delivery_address'] = str(order.delivery_address)[:500]  # Stripe metadata limit
            
            intent_params = {
                'amount': amount_cents,
                'currency': 'usd',
                'metadata': metadata,
                'payment_method_types': payment_method_types,
                'capture_method': 'automatic',
                'confirmation_method': 'automatic',
            }
            
            # Add return URL if provided
            if return_url:
                intent_params['return_url'] = return_url
            
            # Create customer in Stripe if user exists
            stripe_customer_id = None
            if hasattr(order, 'user') and order.user and order.user.email:
                try:
                    customer = stripe.Customer.create(
                        email=order.user.email,
                        name=order.user.get_full_name() or order.user.username,
                        metadata={'user_id': str(order.user.id)}
                    )
                    stripe_customer_id = customer.id
                    intent_params['customer'] = stripe_customer_id
                except stripe.error.StripeError as e:
                    logger.warning(f"Failed to create Stripe customer: {e}")
            
            intent = stripe.PaymentIntent.create(**intent_params)
            
            payment_intent = StripePaymentIntent.objects.create(
                order=order,
                stripe_payment_intent_id=intent.id,
                amount_cents=amount_cents,
                currency='usd',
                status=intent.status,
                client_secret=intent.client_secret,
                stripe_customer_id=stripe_customer_id,
            )
            
            logger.info(f"Created PaymentIntent {intent.id} for order {order.id} (${order.total})")
            return payment_intent
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating PaymentIntent for order {order.id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error creating PaymentIntent for order {order.id}: {e}")
            raise
    
    @staticmethod
    def create_refund(payment_intent: StripePaymentIntent, amount_cents: int = None, reason: str = None) -> PaymentRefund:
        """
        Create a refund for a payment intent.
        """
        try:
            refund_amount = amount_cents or payment_intent.amount_cents
            
            refund = stripe.Refund.create(
                payment_intent=payment_intent.stripe_payment_intent_id,
                amount=refund_amount,
                reason=reason or 'requested_by_customer',
                metadata={
                    'order_id': str(payment_intent.order.id),
                    'original_amount': str(payment_intent.amount_cents),
                    'refund_amount': str(refund_amount),
                }
            )
            
            payment_refund = PaymentRefund.objects.create(
                payment_intent=payment_intent,
                stripe_refund_id=refund.id,
                amount_cents=refund_amount,
                reason=reason or 'requested_by_customer',
                status=refund.status,
            )
            
            logger.info(f"Created refund {refund.id} for PaymentIntent {payment_intent.stripe_payment_intent_id}")
            return payment_refund
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating refund: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error creating refund: {e}")
            raise
    
    @staticmethod
    def get_payment_analytics(start_date=None, end_date=None) -> dict:
        """
        Get comprehensive payment analytics for the specified date range.
        """
        from django.utils import timezone
        from datetime import timedelta
        
        if not start_date:
            start_date = timezone.now() - timedelta(days=30)
        if not end_date:
            end_date = timezone.now()
        
        payment_intents = StripePaymentIntent.objects.filter(
            created_at__range=[start_date, end_date]
        )
        
        total_revenue = sum(pi.amount_dollars for pi in payment_intents.filter(status='succeeded'))
        total_transactions = payment_intents.count()
        successful_transactions = payment_intents.filter(status='succeeded').count()
        failed_transactions = payment_intents.filter(status='failed').count()
        
        refunds = PaymentRefund.objects.filter(
            created_at__range=[start_date, end_date]
        )
        total_refunded = sum(r.amount_dollars for r in refunds)
        
        return {
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
            },
            'revenue': {
                'total_revenue': float(total_revenue),
                'net_revenue': float(total_revenue - total_refunded),
                'total_refunded': float(total_refunded),
            },
            'transactions': {
                'total_transactions': total_transactions,
                'successful_transactions': successful_transactions,
                'failed_transactions': failed_transactions,
                'success_rate': (successful_transactions / total_transactions * 100) if total_transactions > 0 else 0,
            },
            'refunds': {
                'total_refunds': refunds.count(),
                'refund_rate': (refunds.count() / successful_transactions * 100) if successful_transactions > 0 else 0,
            }
        }
    
    @staticmethod
    def process_payment_method_update(customer_id: str, payment_method_id: str) -> bool:
        """
        Update the default payment method for a customer.
        """
        try:
            stripe.Customer.modify(
                customer_id,
                invoice_settings={'default_payment_method': payment_method_id}
            )
            
            stripe.PaymentMethod.attach(
                payment_method_id,
                customer=customer_id
            )
            
            logger.info(f"Updated payment method {payment_method_id} for customer {customer_id}")
            return True
            
        except stripe.error.StripeError as e:
            logger.error(f"Failed to update payment method: {e}")
            return False
    
    @staticmethod
    def create_setup_intent(customer_id: str = None, usage: str = 'off_session') -> dict:
        """
        Create a SetupIntent for saving payment methods for future use.
        """
        try:
            setup_intent_params = {
                'usage': usage,
                'payment_method_types': ['card'],
            }
            
            if customer_id:
                setup_intent_params['customer'] = customer_id
            
            setup_intent = stripe.SetupIntent.create(**setup_intent_params)
            
            return {
                'client_secret': setup_intent.client_secret,
                'setup_intent_id': setup_intent.id,
                'status': setup_intent.status,
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create SetupIntent: {e}")
            raise
    
    @staticmethod
    def get_customer_payment_methods(customer_id: str) -> list:
        """
        Retrieve all payment methods for a customer.
        """
        try:
            payment_methods = stripe.PaymentMethod.list(
                customer=customer_id,
                type='card'
            )
            
            return [{
                'id': pm.id,
                'type': pm.type,
                'card': {
                    'brand': pm.card.brand,
                    'last4': pm.card.last4,
                    'exp_month': pm.card.exp_month,
                    'exp_year': pm.card.exp_year,
                } if pm.card else None,
                'created': pm.created,
            } for pm in payment_methods.data]
            
        except stripe.error.StripeError as e:
            logger.error(f"Failed to retrieve payment methods for customer {customer_id}: {e}")
            return []
    
    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """
        Verify Stripe webhook signature for security.
        
        Args:
            payload: Raw webhook payload
            signature: Stripe signature header
        
        Returns:
            True if signature is valid, False otherwise
        """
        if not self.stripe_webhook_secret:
            logger.warning("Stripe webhook secret not configured")
            return False
        
        try:
            stripe.Webhook.construct_event(
                payload, signature, self.stripe_webhook_secret
            )
            return True
        except (stripe.error.SignatureVerificationError, ValueError) as e:
            logger.error(f"Webhook signature verification failed: {e}")
            return False
    
    @transaction.atomic
    def process_webhook_event(self, event_data: Dict[str, Any]) -> bool:
        """
        Process Stripe webhook event with idempotency and comprehensive error handling.
        
        Args:
            event_data: Stripe event data
        
        Returns:
            True if processed successfully, False otherwise
        """
        event_id = event_data.get('id')
        event_type = event_data.get('type')
        
        if not event_id or not event_type:
            logger.error("Invalid webhook event data: missing id or type")
            return False
        
        # Check for duplicate processing
        webhook_event, created = StripeWebhookEvent.objects.get_or_create(
            stripe_event_id=event_id,
            defaults={
                'event_type': event_type,
                'event_data': event_data,
            }
        )
        
        if not created and webhook_event.processed:
            logger.info(f"Webhook event {event_id} already processed, skipping")
            return True
        
        # Increment processing attempts
        webhook_event.increment_attempts()
        
        try:
            # Process different event types
            success = False
            
            if event_type == 'payment_intent.succeeded':
                success = self._handle_payment_intent_succeeded(event_data, webhook_event)
            elif event_type == 'payment_intent.payment_failed':
                success = self._handle_payment_intent_failed(event_data, webhook_event)
            elif event_type == 'payment_intent.canceled':
                success = self._handle_payment_intent_canceled(event_data, webhook_event)
            elif event_type == 'checkout.session.completed':
                success = self._handle_checkout_session_completed(event_data, webhook_event)
            elif event_type == 'charge.dispute.created':
                success = self._handle_charge_dispute_created(event_data, webhook_event)
            else:
                logger.info(f"Unhandled webhook event type: {event_type}")
                success = True  # Mark as processed to avoid retries
            
            if success:
                webhook_event.mark_processed()
                logger.info(f"Successfully processed webhook event {event_id} ({event_type})")
            
            return success
            
        except Exception as e:
            error_msg = f"Error processing webhook event {event_id}: {e}"
            logger.error(error_msg)
            webhook_event.increment_attempts(error_msg)
            return False
    
    def _handle_payment_intent_succeeded(self, event_data: Dict[str, Any], webhook_event: StripeWebhookEvent) -> bool:
        """
        Handle successful payment intent.
        """
        payment_intent_data = event_data.get('data', {}).get('object', {})
        stripe_payment_intent_id = payment_intent_data.get('id')
        
        if not stripe_payment_intent_id:
            logger.error("Missing payment intent ID in webhook data")
            return False
        
        try:
            # Update local payment intent
            payment_intent = StripePaymentIntent.objects.get(
                stripe_payment_intent_id=stripe_payment_intent_id
            )
            
            payment_intent.status = 'succeeded'
            payment_intent.confirmed_at = timezone.now()
            payment_intent.last_webhook_event_id = webhook_event.stripe_event_id
            
            # Update payment method details if available
            charges = payment_intent_data.get('charges', {}).get('data', [])
            if charges:
                charge = charges[0]
                payment_method = charge.get('payment_method_details', {})
                payment_intent.payment_method_type = payment_method.get('type', '')
                payment_intent.payment_method_id = charge.get('payment_method', '')
            
            payment_intent.save()
            webhook_event.payment_intent = payment_intent
            webhook_event.save()
            
            # Mark associated order as paid if exists
            if payment_intent.order:
                mark_order_as_paid(payment_intent.order)
                logger.info(f"Marked order {payment_intent.order.id} as paid")
            
            return True
            
        except StripePaymentIntent.DoesNotExist:
            logger.error(f"Payment intent {stripe_payment_intent_id} not found in database")
            return False
        except Exception as e:
            logger.error(f"Error handling payment success: {e}")
            return False
    
    def _handle_payment_intent_failed(self, event_data: Dict[str, Any], webhook_event: StripeWebhookEvent) -> bool:
        """
        Handle failed payment intent.
        """
        payment_intent_data = event_data.get('data', {}).get('object', {})
        stripe_payment_intent_id = payment_intent_data.get('id')
        
        if not stripe_payment_intent_id:
            return False
        
        try:
            payment_intent = StripePaymentIntent.objects.get(
                stripe_payment_intent_id=stripe_payment_intent_id
            )
            
            payment_intent.status = 'requires_payment_method'  # Allow retry
            payment_intent.last_webhook_event_id = webhook_event.stripe_event_id
            payment_intent.save()
            
            webhook_event.payment_intent = payment_intent
            webhook_event.save()
            
            logger.info(f"Payment intent {stripe_payment_intent_id} failed, marked for retry")
            return True
            
        except StripePaymentIntent.DoesNotExist:
            logger.error(f"Payment intent {stripe_payment_intent_id} not found")
            return False
    
    def _handle_payment_intent_canceled(self, event_data: Dict[str, Any], webhook_event: StripeWebhookEvent) -> bool:
        """
        Handle canceled payment intent.
        """
        payment_intent_data = event_data.get('data', {}).get('object', {})
        stripe_payment_intent_id = payment_intent_data.get('id')
        
        if not stripe_payment_intent_id:
            return False
        
        try:
            payment_intent = StripePaymentIntent.objects.get(
                stripe_payment_intent_id=stripe_payment_intent_id
            )
            
            payment_intent.status = 'canceled'
            payment_intent.last_webhook_event_id = webhook_event.stripe_event_id
            payment_intent.save()
            
            webhook_event.payment_intent = payment_intent
            webhook_event.save()
            
            logger.info(f"Payment intent {stripe_payment_intent_id} canceled")
            return True
            
        except StripePaymentIntent.DoesNotExist:
            logger.error(f"Payment intent {stripe_payment_intent_id} not found")
            return False

    def _handle_checkout_session_completed(self, event_data: Dict[str, Any], webhook_event: StripeWebhookEvent) -> bool:
        """Finalize orders for Checkout Session completion."""
        session = event_data.get('data', {}).get('object', {})
        # Try both metadata.order_id and client_reference_id
        order_id = None
        md = session.get('metadata') or {}
        if md.get('order_id'):
            order_id = md.get('order_id')
        elif session.get('client_reference_id'):
            order_id = session.get('client_reference_id')
        if not order_id:
            logger.error("checkout.session.completed missing order_id metadata")
            return False
        try:
            order = Order.objects.select_related('table').get(id=int(order_id))
        except Exception:
            logger.error("Order %s not found for checkout.session.completed", order_id)
            return False

        # Idempotency: if already paid, skip
        if getattr(order, 'status', '').upper() in {'PAID', 'COMPLETED'} or getattr(order, 'paid_at', None):
            return True

        # Mark paid and persist invoice
        try:
            mark_order_as_paid(order)
        except Exception:
            logger.exception("Failed to mark order %s as paid", order.id)

        # Create short reservation(s) for dine-in if applicable
        try:
            from django.conf import settings as dj_settings
            from django.utils import timezone
            reserve_minutes = int(getattr(dj_settings, 'TABLE_RESERVE_MINUTES', 30) or 30)
            if getattr(order, 'delivery_option', '') == getattr(Cart, 'DELIVERY_DINE_IN', 'DINE_IN') and getattr(order, 'table_id', None):
                from reservations.models import Reservation
                from core.models import Table
                now = timezone.now()
                start = now + timezone.timedelta(minutes=16)
                ends = start + timezone.timedelta(minutes=reserve_minutes)
                # Build list of table ids: primary + extras from metadata
                table_ids = []
                try:
                    table_ids.append(int(order.table_id))
                except Exception:
                    pass
                try:
                    meta_tbls = []
                    if isinstance(order.metadata, dict):
                        meta_tbls = order.metadata.get('tables') or []
                    sc = getattr(order, 'source_cart', None)
                    if not meta_tbls and sc and isinstance(sc.metadata, dict):
                        meta_tbls = sc.metadata.get('tables') or []
                    for tid in meta_tbls:
                        t = int(tid)
                        if t not in table_ids:
                            table_ids.append(t)
                except Exception:
                    pass

                for tid in table_ids:
                    try:
                        t = Table.objects.get(pk=tid)
                        Reservation.objects.get_or_create(
                            location=t.location,
                            table=t,
                            created_by=getattr(order, 'user', None),
                            defaults={
                                'guest_name': (getattr(order, 'customer_name', '') or ''),
                                'guest_phone': (getattr(order, 'customer_phone', '') or ''),
                                'party_size': 2,
                                'start_time': start,
                                'end_time': ends,
                                'status': 'confirmed',
                            }
                        )
                    except Exception:
                        logger.exception("Failed to reserve table %s for order %s", tid, order.id)
        except Exception:
            logger.exception("Failed to create reservation for order %s", order.id)

        # Clear source cart
        try:
            sc = getattr(order, 'source_cart', None)
            if sc:
                sc.items.all().delete()
                sc.status = getattr(Cart, 'STATUS_CONVERTED', 'converted')
                sc.save(update_fields=['status', 'updated_at'])
        except Exception:
            logger.exception("Failed to clear cart for order %s", order.id)

        # Optional POS print webhook
        try:
            from django.conf import settings as dj_settings
            pos_url = getattr(dj_settings, 'POS_PRINTER_URL', '')
            if pos_url:
                import json as _json, requests  # type: ignore
                payload = {
                    'order_id': order.id,
                    'total': str(getattr(order, 'total_amount', getattr(order, 'total', '0.00'))),
                    'paid_at': getattr(order, 'paid_at', None).isoformat() if getattr(order, 'paid_at', None) else None,
                }
                try:
                    requests.post(pos_url, data=_json.dumps(payload), headers={'Content-Type':'application/json'}, timeout=3)
                except Exception:
                    logger.warning("POS printer hook failed for order %s", order.id)
        except Exception:
            pass

        return True
    
    def _handle_charge_dispute_created(self, event_data: Dict[str, Any], webhook_event: StripeWebhookEvent) -> bool:
        """
        Handle charge dispute creation.
        """
        dispute_data = event_data.get('data', {}).get('object', {})
        charge_id = dispute_data.get('charge')
        
        if charge_id:
            logger.warning(f"Dispute created for charge {charge_id}")
            # Here you could implement dispute handling logic
            # such as notifying admins, updating order status, etc.
        
        return True
    
    @transaction.atomic
    def create_refund(
        self,
        payment_intent: StripePaymentIntent,
        amount_cents: Optional[int] = None,
        reason: str = '',
        initiated_by=None,
        notes: str = ''
    ) -> PaymentRefund:
        """
        Create a refund for a payment intent.
        
        Args:
            payment_intent: The original payment intent
            amount_cents: Refund amount in cents (None for full refund)
            reason: Reason for refund
            initiated_by: Admin user initiating the refund
            notes: Internal notes
        
        Returns:
            PaymentRefund instance
        
        Raises:
            ValueError: If refund amount is invalid
            stripe.error.StripeError: For Stripe API errors
        """
        if not payment_intent.is_successful():
            raise ValueError("Cannot refund unsuccessful payment")
        
        refund_amount = amount_cents or payment_intent.amount_cents
        
        if refund_amount <= 0 or refund_amount > payment_intent.amount_cents:
            raise ValueError("Invalid refund amount")
        
        try:
            # Create Stripe refund
            stripe_refund = stripe.Refund.create(
                payment_intent=payment_intent.stripe_payment_intent_id,
                amount=refund_amount,
                reason=reason or 'requested_by_customer',
            )
            
            # Create local refund record
            refund = PaymentRefund.objects.create(
                payment_intent=payment_intent,
                stripe_refund_id=stripe_refund.id,
                amount_cents=refund_amount,
                currency=payment_intent.currency,
                status=stripe_refund.status,
                reason=reason,
                initiated_by=initiated_by,
                notes=notes,
            )
            
            logger.info(
                f"Created refund {stripe_refund.id} for ${refund_amount/100:.2f} "
                f"on payment intent {payment_intent.stripe_payment_intent_id}"
            )
            
            return refund
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating refund: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error creating refund: {e}")
            raise
    
    def get_payment_intent_status(self, stripe_payment_intent_id: str) -> Optional[str]:
        """
        Get current status of a payment intent from Stripe.
        
        Args:
            stripe_payment_intent_id: Stripe Payment Intent ID
        
        Returns:
            Current status or None if not found
        """
        try:
            stripe_intent = stripe.PaymentIntent.retrieve(stripe_payment_intent_id)
            return stripe_intent.status
        except stripe.error.StripeError as e:
            logger.error(f"Error retrieving payment intent status: {e}")
            return None
    
    def cancel_payment_intent(self, payment_intent: StripePaymentIntent) -> bool:
        """
        Cancel a payment intent if possible.
        
        Args:
            payment_intent: Payment intent to cancel
        
        Returns:
            True if canceled successfully, False otherwise
        """
        if not payment_intent.can_be_canceled():
            logger.warning(f"Payment intent {payment_intent.stripe_payment_intent_id} cannot be canceled")
            return False
        
        try:
            stripe.PaymentIntent.cancel(payment_intent.stripe_payment_intent_id)
            payment_intent.status = 'canceled'
            payment_intent.save(update_fields=['status'])
            
            logger.info(f"Canceled payment intent {payment_intent.stripe_payment_intent_id}")
            return True
            
        except stripe.error.StripeError as e:
            logger.error(f"Error canceling payment intent: {e}")
            return False


# Global service instance
stripe_service = StripePaymentService()
