from django.urls import path

from .views import WalkDetailView

urlpatterns = [
    path('shift/<int:pk>/walk', WalkDetailView.as_view(), name='walk-list'),
]
