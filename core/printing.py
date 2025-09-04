from __future__ import annotations

from io import BytesIO
from decimal import Decimal
from typing import Any, Dict

from django.template.loader import render_to_string
from django.utils import timezone


def _render_html_to_pdf_bytes(html: str) -> BytesIO:
    """
    Try to render HTML to a PDF BytesIO using optional libraries.
    Falls back to returning the HTML bytes if no PDF engine is available.
    """
    # Try WeasyPrint first
    try:
        from weasyprint import HTML  # type: ignore

        pdf_io = BytesIO()
        HTML(string=html).write_pdf(pdf_io)
        pdf_io.seek(0)
        return pdf_io
    except Exception:
        pass

    # Try xhtml2pdf (pisa)
    try:
        from xhtml2pdf import pisa  # type: ignore

        pdf_io = BytesIO()
        pisa.CreatePDF(src=html, dest=pdf_io)  # returns pisaStatus, ignore for now
        pdf_io.seek(0)
        return pdf_io
    except Exception:
        pass

    # Fallback: return HTML bytes (not a true PDF but useful for debugging)
    bio = BytesIO(html.encode("utf-8"))
    bio.seek(0)
    return bio


def _order_context(order) -> Dict[str, Any]:
    items = []
    try:
        iters = order.items.select_related("menu_item").all()
    except Exception:
        iters = getattr(order, "items", [])
    for it in iters:
        try:
            name = getattr(getattr(it, "menu_item", None), "name", None) or getattr(it, "name", f"Item {getattr(it, 'id', '')}")
        except Exception:
            name = f"Item {getattr(it, 'id', '')}"
        qty = int(getattr(it, "quantity", 0) or 0)
        unit = Decimal(str(getattr(it, "unit_price", 0) or 0))
        items.append({
            "name": name,
            "qty": qty,
            "unit": unit,
            "line_total": unit * qty,
        })
    return {
        "order": order,
        "items": items,
        "now": timezone.localtime(timezone.now()),
    }


def generate_kitchen_ticket_pdf(order) -> BytesIO:
    """
    Render a simple kitchen ticket PDF for the given order using
    templates/printing/kitchen_ticket.html. Returns a BytesIO (PDF bytes
    if a backend is available; otherwise HTML bytes for debugging).
    """
    html = render_to_string("printing/kitchen_ticket.html", _order_context(order))
    return _render_html_to_pdf_bytes(html)


def generate_invoice_pdf(order) -> BytesIO:
    """
    Render a very simple invoice document. Uses a basic inline template
    to avoid introducing new template files. Returns BytesIO.
    """
    # Minimal HTML invoice
    lines = [
        "<html><head><meta charset='utf-8'><style>body{font-family:sans-serif} table{width:100%;border-collapse:collapse} th,td{border:1px solid #eee;padding:6px;text-align:left}</style></head><body>",
        f"<h2>Invoice for Order #{getattr(order, 'order_number', getattr(order, 'id', '?'))}</h2>",
        f"<p>Date: {timezone.localtime(getattr(order, 'created_at', timezone.now())):%Y-%m-%d %H:%M}</p>",
        "<table><thead><tr><th>Item</th><th>Qty</th><th>Unit</th><th>Total</th></tr></thead><tbody>",
    ]
    try:
        iters = order.items.select_related("menu_item").all()
    except Exception:
        iters = getattr(order, "items", [])
    total = Decimal("0.00")
    for it in iters:
        try:
            name = getattr(getattr(it, "menu_item", None), "name", None) or getattr(it, "name", f"Item {getattr(it, 'id', '')}")
        except Exception:
            name = f"Item {getattr(it, 'id', '')}"
        qty = int(getattr(it, "quantity", 0) or 0)
        unit = Decimal(str(getattr(it, "unit_price", 0) or 0))
        line_total = unit * qty
        total += line_total
        lines.append(f"<tr><td>{name}</td><td>{qty}</td><td>{unit}</td><td>{line_total}</td></tr>")
    lines.append("</tbody></table>")
    # Order summary
    try:
        tax = Decimal(str(getattr(order, "tax_amount", 0) or 0))
    except Exception:
        tax = Decimal("0.00")
    try:
        tips = Decimal(str(getattr(order, "tip_amount", 0) or 0))
    except Exception:
        tips = Decimal("0.00")
    try:
        grand = getattr(order, "grand_total", None)
        if callable(grand):
            grand_total = Decimal(str(grand() or total))
        else:
            grand_total = Decimal(str(getattr(order, "total_amount", getattr(order, "total", total)) or total))
    except Exception:
        grand_total = total
    lines.append("<hr>")
    lines.append(f"<p>Subtotal: {total}</p>")
    if tax:
        lines.append(f"<p>Tax: {tax}</p>")
    if tips:
        lines.append(f"<p>Tip: {tips}</p>")
    lines.append(f"<h3>Total: {grand_total}</h3>")
    lines.append("</body></html>")
    html = "".join(lines)
    return _render_html_to_pdf_bytes(html)

