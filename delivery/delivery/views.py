# from django.shortcuts import render
from django.views.generic.detail import DetailView

from .models import Shift

class WalkDetailView(DetailView):
    template_name = 'delivery/walk.html'
    model = Shift
