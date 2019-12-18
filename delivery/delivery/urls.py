from django.urls import path

from .views import (
    WalkDetailView,
    OrderDetailView,
    CreateOnfleetOrderView,
    CreateOnfleetShiftView,
    OnfleetTruckView,
    NewOrderView,
)

urlpatterns = [
    path('shift/<int:pk>/walk', WalkDetailView.as_view(), name='walk-list'),
    path('shift/<int:pk>/onfleet', CreateOnfleetShiftView, name='onfleet-shift'),
    path('deliveries/<int:pk>/sheet', OrderDetailView.as_view(), name='order-sheet'),
    path('deliveries/<int:pk>/onfleet', CreateOnfleetOrderView, name='onfleet-order'),
    path('trucks', OnfleetTruckView, name='truck-view'),
    path('orders/new', NewOrderView, name='new-orders'),
]
