# payments/urls.py
from __future__ import annotations

from django.urls import path

from . import views

urlpatterns = [
    path("checkout/", views.checkout, name="checkout"),
    path("webhook/", views.webhook, name="webhook"),
]
