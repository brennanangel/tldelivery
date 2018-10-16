from django.urls import path

from .views import WalkDetailView, OrderDetailView

urlpatterns = [
    path('shift/<int:pk>/walk', WalkDetailView.as_view(), name='walk-list'),
    path('deliveries/<int:pk>/sheet', OrderDetailView.as_view(), name='order-sheet'),
]
