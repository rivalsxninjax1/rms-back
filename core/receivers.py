from __future__ import annotations

import os
from pathlib import Path
from django.conf import settings
from django.dispatch import receiver

from payments.post_payment import order_paid
from orders.signals import order_status_changed
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from orders.models import Order
from core.printing import generate_kitchen_ticket_pdf, generate_invoice_pdf


def _ensure_dir(path: Path) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass


def _write_bytesio_to_file(bio, filepath: Path) -> None:
    try:
        with filepath.open('wb') as f:
            f.write(bio.getvalue())
    except Exception:
        # Best-effort only
        pass


@receiver(order_paid)
def on_order_paid_generate_documents(sender, order=None, payment=None, request=None, **kwargs):
    if not order:
        return
    media_root = Path(getattr(settings, 'MEDIA_ROOT', '.'))

    # Always render invoice PDF to /media/invoices/
    invoices_dir = media_root / 'invoices'
    _ensure_dir(invoices_dir)
    invoice_pdf = generate_invoice_pdf(order)
    invoice_path = invoices_dir / f"order_{getattr(order, 'id', 'unknown')}.pdf"
    _write_bytesio_to_file(invoice_pdf, invoice_path)

    # Optionally generate and store a kitchen ticket
    print_tickets = str(getattr(settings, 'PRINT_TICKETS', '0')).strip() in {'1', 'true', 'True'}
    if print_tickets:
        tickets_dir = media_root / 'tickets'
        _ensure_dir(tickets_dir)
        ticket_pdf = generate_kitchen_ticket_pdf(order)
        ticket_path = tickets_dir / f"order_{getattr(order, 'id', 'unknown')}.pdf"
        # Avoid re-writing if exists
        if not ticket_path.exists():
            _write_bytesio_to_file(ticket_pdf, ticket_path)
        # TODO: integrate with actual printing system if PRINTER_NAME is configured

    # Broadcast to WebSocket group "orders"
    try:
        layer = get_channel_layer()
        if layer and order:
            payload = {
                "event": "order_paid",
                "order_id": getattr(order, 'id', None),
                "payment_id": getattr(payment, 'id', None),
            }
            async_to_sync(layer.group_send)(
                "orders", {"type": "broadcast", "data": payload}
            )
    except Exception:
        pass


@receiver(order_status_changed)
def on_status_changed_generate_ticket(sender, order: Order = None, old: str = '', new: str = '', by_user=None, **kwargs):
    if not order or not new:
        return
    # 'in_progress' maps to PREPARING in our real statuses
    if new != Order.STATUS_PREPARING:
        return
    media_root = Path(getattr(settings, 'MEDIA_ROOT', '.'))
    tickets_dir = media_root / 'tickets'
    _ensure_dir(tickets_dir)
    ticket_path = tickets_dir / f"order_{getattr(order, 'id', 'unknown')}.pdf"
    if ticket_path.exists():
        return  # already generated
    ticket_pdf = generate_kitchen_ticket_pdf(order)
    _write_bytesio_to_file(ticket_pdf, ticket_path)

    # Also broadcast to WebSocket group "orders"
    try:
        layer = get_channel_layer()
        if layer and order:
            payload = {
                "event": "order_status_changed",
                "order_id": getattr(order, 'id', None),
                "old": old,
                "new": new,
            }
            async_to_sync(layer.group_send)(
                "orders", {"type": "broadcast", "data": payload}
            )
    except Exception:
        pass
