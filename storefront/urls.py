# rms-back/storefront/urls.py
from django.urls import path
from . import views

app_name = "storefront"

urlpatterns = [
    path("", views.menu_list, name="menu_list"),
    path("item/<slug:slug>/", views.item_detail, name="item_detail"),
    path("cart/", views.cart_full, name="cart_full"),
    path("cart/bar/", views.cart_bar, name="cart_bar"),
    path("cart/add/", views.cart_add, name="cart_add"),
    path("cart/update/", views.cart_update, name="cart_update"),
    path("cart/remove/", views.cart_remove, name="cart_remove"),
    path("cart/extras/", views.cart_extras, name="cart_extras"),
    path("cart/extras/modal/", views.cart_extras_modal, name="cart_extras_modal"),
    path("cart/table-modal/", views.cart_table_modal, name="cart_table_modal"),
    path("cart/seed-tables/", views.cart_seed_tables, name="cart_seed_tables"),
    path("cart/coupon/", views.cart_coupon, name="cart_coupon"),
    path("cart/option/", views.cart_option, name="cart_option"),
    path("cart/tip/", views.cart_tip, name="cart_tip"),
    path("cart/checkout/", views.cart_checkout, name="cart_checkout"),
    path("cart/merge-session/", views.cart_merge_session, name="cart_merge_session"),
    path("cart/clear/", views.cart_clear, name="cart_clear"),
    path("my-orders/", views.my_orders, name="my_orders"),
    path("reservations/", views.reservations_list, name="reservations_list"),
]
