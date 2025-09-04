import pytest
from datetime import datetime, timedelta
from django.utils import timezone
from rest_framework.test import APIClient

from tests.factories import LocationFactory
from core.models import Table
from reservations.models import Reservation


@pytest.mark.django_db
def test_table_availability_busy_and_free_blocks(api_client: APIClient):
    loc = LocationFactory()
    t1 = Table.objects.create(location=loc, table_number="A1", capacity=4, is_active=True)
    t2 = Table.objects.create(location=loc, table_number="A2", capacity=2, is_active=True)

    # Window: today 18:00 → 20:00 local time
    today = timezone.localdate()
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(today, datetime.min.time()).replace(hour=18, minute=0), tz)
    end = timezone.make_aware(datetime.combine(today, datetime.min.time()).replace(hour=20, minute=0), tz)

    # Busy reservations on t1: 18:15-18:45 and 19:00-19:30
    Reservation.objects.create(
        location=loc,
        table=t1,
        start_time=start + timedelta(minutes=15),
        end_time=start + timedelta(minutes=45),
        reservation_date=today,
        status=Reservation.STATUS_CONFIRMED,
        party_size=2,
    )
    r2 = Reservation.objects.create(
        location=loc,
        table=t1,
        start_time=start + timedelta(minutes=60),
        end_time=start + timedelta(minutes=90),
        reservation_date=today,
        status=Reservation.STATUS_PENDING,
        party_size=2,
    )
    # A cancelled reservation should not block
    Reservation.objects.create(
        location=loc,
        table=t1,
        start_time=start + timedelta(minutes=90),
        end_time=start + timedelta(minutes=110),
        reservation_date=today,
        status=Reservation.STATUS_CANCELLED,
        party_size=2,
    )

    # Call endpoint with date/from/to
    resp = api_client.get(
        f"/api/reservations/tables/availability/?location={loc.id}&date={today.isoformat()}&from=18:00&to=20:00"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["start"].startswith(f"{today.isoformat()}T18:00")
    assert data["end"].startswith(f"{today.isoformat()}T20:00")

    by_id = {t["table_id"]: t for t in data["tables"]}
    assert t1.id in by_id and t2.id in by_id

    # t1 busy blocks include two entries, second with our r2 id
    t1_block = by_id[t1.id]
    assert len(t1_block["busy"]) == 2
    assert any(b.get("reservation_id") == r2.id for b in t1_block["busy"])
    # Free blocks should fill [18:00-18:15], [18:45-19:00], [19:30-20:00]
    free = t1_block["free"]
    free_ranges = [(f["start"], f["end"]) for f in free]
    assert any(s.endswith("T18:00:00") and e.endswith("T18:15:00") for s, e in free_ranges)
    assert any(s.endswith("T18:45:00") and e.endswith("T19:00:00") for s, e in free_ranges)
    assert any(s.endswith("T19:30:00") and e.endswith("T20:00:00") for s, e in free_ranges)

    # t2 has no reservations → a single free block equals full window
    t2_block = by_id[t2.id]
    assert t2_block["busy"] == []
    assert len(t2_block["free"]) == 1
    assert t2_block["free"][0]["start"].endswith("T18:00:00")
    assert t2_block["free"][0]["end"].endswith("T20:00:00")

