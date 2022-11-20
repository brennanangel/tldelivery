from django.contrib import admin
from django.urls import path

from .views import (
    CreateOnfleetOrderView,
    CreateOnfleetShiftView,
    NewOrderView,
    OnfleetTruckView,
    OrderDetailView,
    ShopifyReconciliationView,
    WalkDetailView,
)

urlpatterns = [
    path("shift/<int:pk>/walk", WalkDetailView.as_view(), name="walk-list"),
    path("shift/<int:pk>/onfleet", CreateOnfleetShiftView, name="onfleet-shift"),
    path("deliveries/<int:pk>/sheet", OrderDetailView.as_view(), name="order-sheet"),
    path("deliveries/<int:pk>/onfleet", CreateOnfleetOrderView, name="onfleet-order"),
    path("trucks", OnfleetTruckView, name="truck_view"),
    path("deliveries/shopify", ShopifyReconciliationView, name="shopify_view"),
    path("orders/new", admin.site.admin_view(NewOrderView), name="new_orders"),
]
