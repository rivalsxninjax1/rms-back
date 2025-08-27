from django.urls import path
from .views import loyalty_preview

app_name = "loyality"

urlpatterns = [
    path("preview/", loyalty_preview, name="preview"),
]
