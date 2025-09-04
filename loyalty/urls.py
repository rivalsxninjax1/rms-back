"""New loyalty URLs module that proxies the legacy loyality URLs.

Keeps path names stable while allowing new include(("loyalty.urls", ...)).
"""
from importlib import import_module

legacy = import_module("loyality.urls")

app_name = "loyalty"
urlpatterns = getattr(legacy, "urlpatterns", [])

