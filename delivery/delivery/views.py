# from django.shortcuts import render
import traceback
import datetime
from django.views.generic.detail import DetailView
from django.contrib.admin.views.main import ChangeList
from django.http import HttpResponse, HttpResponseNotFound
from django.views.decorators.http import require_POST
from django.shortcuts import render
from django.template.defaulttags import register
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.template.response import TemplateResponse
from django.core.paginator import Paginator
from django.urls import reverse
from django.utils.html import mark_safe

from .models import Shift, Delivery
from .actions import (
    create_onfleet_task_from_order,
    create_onfleet_tasks_from_shift,
    get_onfleet_trucks,
    search_clover_orders,
)
from .admin import DeliveryAdmin


@register.filter(name="lookup")
def lookup(d, key):
    return d.get(key)


class WalkDetailView(LoginRequiredMixin, DetailView):
    template_name = "delivery/walk.html"
    model = Shift


class OrderDetailView(LoginRequiredMixin, DetailView):
    template_name = "delivery/order.html"
    model = Delivery


@require_POST
@login_required
def CreateOnfleetOrderView(request, pk):
    try:
        order = Delivery.objects.get(pk=pk)
    except Delivery.DoesNotExist:
        raise HttpResponseNotFound("Not Found")
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
        raise HttpResponseNotFound("Not Found")
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
    if tasks is None or not tasks:
        return HttpResponse("No deliveries found.")
    return render(
        request,
        "delivery/trucks.html",
        {"teams": teams, "workers": workers, "tasks": tasks,},
    )


class NewOrderChangeList(ChangeList):
    def get_results(self, request):
        result_list = search_clover_orders(datetime.date.today())
        result_count = len(result_list)

        self.result_count = result_count
        self.show_full_result_count = True
        self.show_admin_actions = False
        self.full_result_count = result_count
        self.result_list = result_list
        self.can_show_all = True
        self.multi_page = None
        self.paginator = Paginator(result_list, 100)


class NewOrderAdmin(DeliveryAdmin):
    def save(self, obj):
        if getattr(obj, "delivery_shift", None):
            text = "Save"
            target = "_self"
        else:
            text = "Save As"
            target = "_blank"
        url = f'{reverse(f"admin:{self.model._meta.app_label}_{self.model._meta.model_name}_add")}?order_number={obj.order_number}'
        return mark_safe(
            f'<a class="btn btn-primary" href="{url}" target="{target}">{text}</a>'
        )


@login_required
def NewOrderView(request):
    list_display = (
        "created_at",
        "order_number",
        "recipient_name",
        "delivery_shift",
        "save",
    )
    list_editable = ("delivery_shift",)
    list_filter = ()
    search_fields = ("order_number", "recipient_last_name")
    model_admin = NewOrderAdmin(Delivery, None)
    model_admin.empty_value_display = " - "
    cl = NewOrderChangeList(
        request,
        Delivery,
        list_display,
        None,  # list_display_links
        list_filter,  # list_filter
        None,  # date_hierarchy
        search_fields,
        None,  # list_select_related
        100,  # list_per_page
        200,  # list_max_show_all
        list_editable,
        model_admin,
    )
    cl.formset = None
    context = {
        "module_name": "Orders",
        "title": "New Orders",
        "is_popup": False,
        "to_field": cl.to_field,
        "cl": cl,
        "media": model_admin.media,
        "has_add_permission": False,
        "opts": cl.opts,
        "preserved_filters": model_admin.get_preserved_filters(request),
    }

    request.current_app = "Orders"

    return TemplateResponse(request, "admin/change_list.html", context)

