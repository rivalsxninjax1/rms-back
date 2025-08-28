# reservations/urls.py
from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import TableViewSet, ReservationViewSet

app_name = "reservations"

router = DefaultRouter()
router.register(r"reservations/tables", TableViewSet, basename="reservations-tables")
router.register(r"reservations", ReservationViewSet, basename="reservations")

urlpatterns = [
    path("", include(router.urls)),
]
