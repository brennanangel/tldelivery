# from django.shortcuts import render
import traceback
import datetime
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView
from django.http import HttpResponse, HttpResponseNotFound
from django.views.decorators.http import require_POST
from django.shortcuts import render
from django.template.defaulttags import register
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required

from .models import Shift, Delivery
from .actions import (
    create_onfleet_task_from_order,
    create_onfleet_tasks_from_shift,
    get_onfleet_trucks,
    search_clover_orders
)

@register.filter(name='lookup')
def lookup(d, key):
    return d.get(key)

class WalkDetailView(LoginRequiredMixin, DetailView):
    template_name = 'delivery/walk.html'
    model = Shift

class OrderDetailView(LoginRequiredMixin, DetailView):
    template_name = 'delivery/order.html'
    model = Delivery

@require_POST
@login_required
def CreateOnfleetOrderView(request, pk):
    try:
        order = Delivery.objects.get(pk=pk)
    except Delivery.DoesNotExist:
        raise HttpResponseNotFound('Not Found')
    try:
        create_onfleet_task_from_order(order)
    except Exception as exc:
        return HttpResponse(str(exc), status=500)
    return HttpResponse(status=200)

@require_POST
@login_required
def CreateOnfleetShiftView(request, pk):
    try:
        shift = Shift.objects.get(pk=pk)
    except Shift.DoesNotExist:
        raise HttpResponseNotFound('Not Found')
    try:
        create_onfleet_tasks_from_shift(shift)
    except Exception as exc:
        return HttpResponse(str(exc), status=500)
    return HttpResponse(status=200)

@login_required
def OnfleetTruckView(request):
    try:
        teams, workers, tasks = get_onfleet_trucks()
    except Exception as exc:
        traceback.print_exc()
        return HttpResponse(str(exc), status=500)
    if tasks is None or not len(tasks):
        return HttpResponse('No deliveries found.')
    return render(request, 'delivery/trucks.html', {
        'teams': teams,
        'workers': workers,
        'tasks': tasks,
    })

class NewOrderView(LoginRequiredMixin, ListView):
    model = Delivery
    template_name = 'delivery/new_order_list.html'

    def get_context_data(self, **kwargs):
        context = {
            'object_list': search_clover_orders(datetime.date.today()),
            'is_paginated': False,
        }
        return context
