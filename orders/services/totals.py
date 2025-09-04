from __future__ import annotations

from typing import Optional

from decimal import Decimal


def compute_cart_totals(cart, *, save: bool = True) -> None:
    """Compute all cart-derived monetary fields using the model's canonical logic.

    Centralizes the calculation entry-point so views and signals call a single
    place. Intentionally ignores any client-provided totals.
    """
    # Delegate to the existing robust method on the model
    cart.calculate_totals(save=save)


def compute_order_totals(order, *, save: bool = True) -> None:
    """Compute order totals from items using server-side logic only."""
    order.calculate_totals(save=save)

