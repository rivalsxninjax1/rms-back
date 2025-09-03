# payments/urls.py
from __future__ import annotations

from django.urls import path

from . import views

app_name = 'payments'

urlpatterns = [
    # Payment Intent Management
    path('payment-intent/create/', views.create_payment_intent, name='create_payment_intent'),
    path('payment-intent/<str:payment_intent_id>/status/', views.payment_intent_status, name='payment_intent_status'),
    path('payment-intent/<str:payment_intent_id>/cancel/', views.cancel_payment_intent, name='cancel_payment_intent'),
    
    # Webhook Processing
    path('webhook/', views.stripe_webhook, name='stripe_webhook'),
    
    # Payment Analytics & Reporting
    path('analytics/', views.payment_analytics, name='payment_analytics'),
    
    # Receipt & Invoice Generation
    path('receipt/<int:order_id>/', views.generate_receipt, name='generate_receipt'),
    
    # Refund Management
    path('refund/<int:payment_intent_id>/', views.create_refund, name='create_refund'),
    
    # Payment Method Management
    path('setup-intent/', views.create_setup_intent, name='create_setup_intent'),
    path('customer/<str:customer_id>/payment-methods/', views.customer_payment_methods, name='customer_payment_methods'),
    
    # Legacy endpoints for backward compatibility
    path('checkout/', views.checkout, name='checkout'),
    path('webhook-legacy/', views.webhook, name='webhook_legacy'),

    # Success/Cancel landing pages used by Stripe Checkout
    path('checkout-success/', views.checkout_success, name='checkout-success'),
    path('checkout-cancel/', views.checkout_cancel, name='checkout-cancel'),
]
