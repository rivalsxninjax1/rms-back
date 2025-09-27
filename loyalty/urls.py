from __future__ import annotations

from django.urls import path

from . import views

app_name = "loyalty"

urlpatterns = [
    path("loyalty/preview/", views.loyalty_preview, name="loyalty_preview"),
    path("loyalty/ranks/", views.ranks_list, name="loyalty_ranks"),
]
