import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from orders.models import Order, OrderStatusHistory
from orders.signals import order_status_changed


@pytest.mark.django_db
def test_allowed_transition_sequence_emits_signal_and_writes_history():
    User = get_user_model()
    user = User.objects.create_user(username="u1", password="x")
    order = Order.objects.create(user=user)

    events = []

    def _receiver(sender, order, old, new, by_user, **kwargs):
        events.append((old, new, getattr(by_user, "id", None)))

    order_status_changed.connect(_receiver)
    try:
        # pending -> in_progress
        order.transition_to("in_progress", by_user=user)
        order.refresh_from_db()
        assert order.status == Order.STATUS_PREPARING
        assert order.started_preparing_at is not None
        h = OrderStatusHistory.objects.filter(order=order).first()
        assert h is not None
        assert h.previous_status == Order.STATUS_PENDING
        assert h.new_status == Order.STATUS_PREPARING

        # in_progress -> served
        order.transition_to("served", by_user=user)
        order.refresh_from_db()
        assert order.status == Order.STATUS_READY
        assert order.ready_at is not None

        # served -> completed
        order.transition_to("completed", by_user=user)
        order.refresh_from_db()
        assert order.status == Order.STATUS_COMPLETED
        assert order.completed_at is not None

        # signals captured
        assert len(events) >= 3
        assert events[0][0] == Order.STATUS_PENDING
        assert events[0][1] == Order.STATUS_PREPARING
    finally:
        order_status_changed.disconnect(_receiver)


@pytest.mark.django_db
def test_blocked_transitions_raise_validation_error():
    User = get_user_model()
    user = User.objects.create_user(username="u2", password="x")
    order = Order.objects.create(user=user)

    # pending -> completed (blocked)
    with pytest.raises(ValidationError):
        order.transition_to("completed", by_user=user)

    # pending -> served (blocked)
    with pytest.raises(ValidationError):
        order.transition_to("served", by_user=user)

    # move to in_progress; then try going back (served -> in_progress is blocked)
    order.transition_to("in_progress", by_user=user)
    with pytest.raises(ValidationError):
        order.transition_to("pending", by_user=user)

    # complete flow then further transitions blocked
    order.transition_to("served", by_user=user)
    order.transition_to("completed", by_user=user)
    with pytest.raises(ValidationError):
        order.transition_to("cancelled", by_user=user)

