# storefront/urls.py
from django.urls import path
from . import views
from .views import MenuItemsView, MyOrdersView
from accounts.views import whoami as session_ping  # root-level session ping for JS

app_name = "storefront"

urlpatterns = [
    path("", views.home, name="home"),
    path("about/", views.about, name="about"),
    path("branches/", views.branches, name="branches"),

    path("menu/", MenuItemsView.as_view(), name="menu"),
    path("menu/<int:item_id>/", views.menu_item, name="menu-item"),

    path("cart/", views.cart, name="cart"),
    path("checkout/", views.checkout, name="checkout"),

    path("orders/", views.orders, name="orders"),
    path("my-orders/", MyOrdersView.as_view(), name="my_orders"),

    path("contact/", views.contact, name="contact"),
    path("login/", views.login_page, name="login"),
    path("reservations/", views.reservations, name="reservations"),

    # NEW: save tip to session (kept from original)
    path("api/cart/tip/", views.api_cart_set_tip, name="api_cart_set_tip"),

    # NEW: session/CSRF ping for frontend JS (safe alias to accounts.whoami)
    path("session/ping/", session_ping, name="session_ping"),
]
