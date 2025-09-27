from __future__ import annotations

from django.urls import path

from .views import loyalty_preview, ranks_list

app_name = "loyality"

urlpatterns = [
    # Keep these paths stable for the frontend that calls /api/loyality/...
    path("loyalty/preview/", loyalty_preview, name="loyalty_preview"),
    path("loyalty/ranks/", ranks_list, name="loyalty_ranks"),
]
