from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List

from django.contrib import admin, messages
from django.db.models import Sum
from django.http import HttpRequest, HttpResponse
from django.template.response import TemplateResponse
from django.urls import path

from .models import (
    Order, OrderItem,
    StripePaymentIntent, StripeWebhookEvent, PaymentRefund,
)
from .services import stripe_service
from reports.models import AuditLog


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("menu_item_id", "name", "unit_amount_cents", "quantity", "line_total_cents")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "status",
        "currency",
        "subtotal_cents",
        "tip_cents",
        "discount_cents",
        "total_cents",
        "delivery",
        "created_at",
    )
    list_filter = ("status", "currency", "delivery", "created_at")
    search_fields = ("id", "user__username", "stripe_session_id", "stripe_payment_intent")
    readonly_fields = ("created_at", "updated_at", "stripe_session_id", "stripe_payment_intent")
    inlines = [OrderItemInline]


@admin.register(StripeWebhookEvent)
class StripeWebhookEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "event_type", "stripe_event_id", "processed", "processing_attempts", "payment_intent")
    list_filter = ("processed", "event_type", "created_at")
    search_fields = ("stripe_event_id", "event_type", "last_error")
    readonly_fields = ("created_at", "processed_at", "event_data", "last_error")

    actions = ("replay_selected", "replay_failures",)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        try:
            AuditLog.log_action(request.user, 'UPDATE' if change else 'CREATE', f"Webhook event {'updated' if change else 'created'}: {obj.stripe_event_id}", content_object=obj, changes=form.changed_data, request=request, category='payments')
        except Exception:
            pass

    def delete_model(self, request, obj):
        try:
            AuditLog.log_action(request.user, 'DELETE', f"Webhook event deleted: {obj.stripe_event_id}", content_object=obj, request=request, category='payments')
        except Exception:
            pass
        super().delete_model(request, obj)

    def replay_selected(self, request: HttpRequest, queryset):
        ok = 0
        for ev in queryset:
            try:
                success = stripe_service.process_webhook_event(ev.event_data)
                if success:
                    ok += 1
            except Exception:
                pass
        self.message_user(request, f"Replayed {ok}/{queryset.count()} events", level=messages.INFO)
        try:
            AuditLog.log_action(request.user, 'UPDATE', f'Replayed {ok}/{queryset.count()} webhook events', request=request, category='payments')
        except Exception:
            pass

    replay_selected.short_description = "Replay selected events"

    def replay_failures(self, request: HttpRequest, queryset):
        failures = queryset.filter(processed=False)
        return self.replay_selected(request, failures)

    replay_failures.short_description = "Replay failures in selection"


@admin.register(StripePaymentIntent)
class StripePaymentIntentAdmin(admin.ModelAdmin):
    list_display = (
        "id", "stripe_payment_intent_id", "amount_cents", "currency", "status", "user", "order_ref", "last_webhook_event_id", "created_at",
    )
    search_fields = ("stripe_payment_intent_id", "user__username")
    list_filter = ("status", "currency", "created_at")
    readonly_fields = ("created_at", "updated_at",)

    actions = ("refresh_status", "refund_full_amount",)
    change_list_template = "admin/payments/stripepaymentintent/change_list.html"

    def order_ref(self, obj: StripePaymentIntent):
        return getattr(obj, "order", None) or getattr(obj, "order_ref", None)

    def refresh_status(self, request: HttpRequest, queryset):
        updated = 0
        for pi in queryset:
            s = stripe_service.get_payment_intent_status(pi.stripe_payment_intent_id)
            if s and s != pi.status:
                pi.status = s
                pi.save(update_fields=["status", "updated_at"])
                updated += 1
        self.message_user(request, f"Updated {updated} payment intents from Stripe", level=messages.INFO)
        try:
            AuditLog.log_action(request.user, 'UPDATE', f'Refreshed status for {updated} payment intents', request=request, category='payments')
        except Exception:
            pass

    refresh_status.short_description = "Refresh status from Stripe"

    def refund_full_amount(self, request: HttpRequest, queryset):
        created = 0
        for pi in queryset:
            try:
                stripe_service.create_refund(pi, amount_cents=None, reason="requested_by_customer", initiated_by=request.user)
                created += 1
            except Exception as e:
                self.message_user(request, f"Refund failed for {pi.id}: {e}", level=messages.ERROR)
        self.message_user(request, f"Initiated {created} refund(s)", level=messages.INFO)
        try:
            AuditLog.log_action(request.user, 'UPDATE', f'Initiated {created} refunds', request=request, category='payments')
        except Exception:
            pass

    refund_full_amount.short_description = "Refund full amount for selected"

    # Reconciliation view mounted under this admin
    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path("reconciliation/", self.admin_site.admin_view(self.reconciliation_view), name="payments_reconciliation"),
        ]
        return custom + urls

    def reconciliation_view(self, request: HttpRequest):
        days = 7
        try:
            days = int(request.GET.get("days", days))
        except Exception:
            pass
        since = datetime.utcnow() - timedelta(days=days)

        stripe_total = StripePaymentIntent.objects.filter(status="succeeded", created_at__gte=since).aggregate(s=Sum("amount_cents")).get("s") or 0
        try:
            from billing.models import Payment as BillingPayment
            cash_total = BillingPayment.objects.filter(status__iexact="completed", created_at__gte=since).aggregate(s=Sum("amount")).get("s") or 0
        except Exception:
            cash_total = 0
        try:
            from orders.models import Order as CoreOrder
            order_total = CoreOrder.objects.filter(payment_status__in=["COMPLETED", "REFUNDED"], created_at__gte=since).aggregate(s=Sum("total_amount")).get("s") or 0
        except Exception:
            order_total = 0

        ctx = dict(
            self.admin_site.each_context(request),
            title="Payments Reconciliation",
            days=days,
            stripe_total=stripe_total / 100.0,
            cash_total=float(cash_total or 0),
            order_total=float(order_total or 0),
        )
        try:
            AuditLog.log_action(request.user, 'VIEW', 'Viewed payments reconciliation', request=request, category='payments')
        except Exception:
            pass
        return TemplateResponse(request, "admin/payments/reconciliation.html", ctx)


@admin.register(PaymentRefund)
class PaymentRefundAdmin(admin.ModelAdmin):
    list_display = ("id", "payment_intent", "amount_cents", "currency", "status", "reason", "initiated_by", "created_at")
    list_filter = ("status", "currency", "created_at")
    search_fields = ("stripe_refund_id",)
    readonly_fields = ("created_at", "processed_at")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        try:
            AuditLog.log_action(request.user, 'UPDATE' if change else 'CREATE', f"Refund {'updated' if change else 'created'}: {obj.stripe_refund_id}", content_object=obj, changes=form.changed_data, request=request, category='payments')
        except Exception:
            pass

    def delete_model(self, request, obj):
        try:
            AuditLog.log_action(request.user, 'DELETE', f"Refund deleted: {obj.stripe_refund_id}", content_object=obj, request=request, category='payments')
        except Exception:
            pass
        super().delete_model(request, obj)


# Note: reconciliation view is exposed under StripePaymentIntent change list "Tools".
