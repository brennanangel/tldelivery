# from django.shortcuts import render
from django.views.generic.detail import DetailView

from .models import Shift, Delivery

class WalkDetailView(DetailView):
    template_name = 'delivery/walk.html'
    model = Shift

class OrderDetailView(DetailView):
    template_name = 'delivery/order.html'
    model = Delivery
