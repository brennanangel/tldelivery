# from django.shortcuts import render
import traceback
import datetime
import re
import os
import dataclasses
from urllib.parse import urlencode
from typing import Dict
from distutils.util import strtobool
from dateutil.parser import parse
from django.views.generic.detail import DetailView
from django.conf import settings
from django.contrib.admin.views.main import ChangeList
from django.contrib.admin import SimpleListFilter, site as admin_site
from django.http import HttpResponse, HttpResponseNotFound
from django.views.decorators.http import require_POST
from django.shortcuts import render
from django.template.defaulttags import register
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.template.response import TemplateResponse
from django.core.paginator import Paginator
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils.encoding import force_str
from django.db.models.functions import Upper


from .models import Shift, Delivery
from .actions import (
    create_onfleet_task_from_order,
    create_onfleet_tasks_from_shift,
    get_onfleet_trucks,
    search_clover_orders,
)
from .shopify import (
    get_data_by_time_range as get_shopify_data_by_time_range,
    ShopifyOrderInfo,
)
from .clover import search_clover_by_dates, parse_shopify_order_number
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
        {
            "teams": teams,
            "workers": workers,
            "tasks": tasks,
        },
    )


@login_required
def ShopifyReconciliationView(request):
    START_DATE = datetime.date(2021, 11, 17)

    def _is_existing(o: ShopifyOrderInfo) -> bool:
        try:
            Delivery.objects.get(online_id=o.online_id)
            return True
        except Delivery.DoesNotExist:
            pass
        try:
            Delivery.objects.get(
                recipient_first_name=o.first_name.strip() if o.first_name else None,
                recipient_last_name=o.last_name.strip() if o.last_name else None,
                delivery_shift_id=o.shift.id if o.shift else None,
            )
            return True
        except Delivery.DoesNotExist:
            pass
        return False

    # get from Shopify
    orders = get_shopify_data_by_time_range(START_DATE, delivery_only=True)
    missing_orders = [dataclasses.asdict(o) for o in orders if not _is_existing(o)]

    # match to Clover
    clover_orders = search_clover_by_dates(
        START_DATE, end_date=datetime.date(2021, 12, 17)
    )
    map_by_name = {}
    for o in clover_orders:
        shopify_name = parse_shopify_order_number(o)
        if shopify_name is None:
            continue
        map_by_name[shopify_name] = o

    order_numbers = []
    for o in missing_orders:
        if o["name"] in map_by_name:
            o["clover_id"] = map_by_name[o["name"]]["id"]
            order_numbers.append(o["clover_id"])
    scheduled_orders = Delivery.objects.annotate(
        clover_id=Upper("order_number")
    ).filter(clover_id__in=order_numbers)
    scheduled_orders_dict = {o.clover_id: o for o in scheduled_orders}
    for o in missing_orders:
        if "clover_id" in o and o["clover_id"] in scheduled_orders_dict:
            o["id"] = scheduled_orders_dict[o["clover_id"]]["id"]

    # report missing
    return render(
        request,
        "delivery/shopify.html",
        {
            "orders": missing_orders,
            "shopify_orders_url": os.path.join(
                settings.SHOPIFY_APP_URL, "admin", "orders"
            ),
        },
    )


class NewOrderChangeList(ChangeList):
    def get_results(self, request):
        params = self.get_filters_params()
        include_processed = strtobool(params.get("include_processed", "False"))
        try:
            start_date = parse(params.get("date", "")).date()
        except ValueError:
            start_date = datetime.date.today()
        result_list = search_clover_orders(
            start_date, include_processed=include_processed
        )
        result_count = len(result_list)

        self.result_count = result_count
        self.show_full_result_count = False
        self.show_admin_actions = False
        self.full_result_count = True
        self.result_list = result_list
        self.can_show_all = False
        self.multi_page = None
        self.paginator = Paginator(result_list, 100)


class NewOrderProcessedFilter(SimpleListFilter):
    title = "Include Processed"
    parameter_name = "include_processed"

    def lookups(self, request, model_admin):
        return [(False, "Unprocessed"), (True, "All")]

    def queryset(self, request, queryset):
        return queryset

    def choices(self, changelist):
        # remove first "All" option
        for lookup, title in self.lookup_choices:
            yield {
                "selected": self.value() == force_str(lookup),
                "query_string": changelist.get_query_string(
                    {self.parameter_name: lookup}, []
                ),
                "display": title,
            }


class SingleDateFilter:
    title = "Date"
    parameter_name = "date"
    template = "admin/filters/date.html"

    def __init__(self, request, params, *__):
        # This dictionary will eventually contain the request's query string
        # parameters actually used by this filter.
        self.used_parameters = {}
        if self.parameter_name in params:
            value = params.pop(self.parameter_name)
            self.used_parameters[self.parameter_name] = value

    def choices(self, *__):
        # Grab only the "all" option.
        return []

    def lookups(self, *__):
        # Dummy, required to show the filter.
        return ((),)

    def has_output(self):
        return True

    def queryset(self, request, queryset):
        return queryset

    def value(self):
        return self.used_parameters.get(self.parameter_name)


class NewOrderAdmin(DeliveryAdmin):
    list_editable = [
        "delivery_shift",
        "order_number",
        "delivery_type",
        "online_id",
        "recipient_phone_number",
    ]
    list_display = [
        "created_at",
        "order_number",
        "recipient_name",
        "recipient_phone_number_formatted",
        "online_order_link",
        "delivery_shift",
        "action",
        "recipient_phone_number",
        "online_id",
    ]
    list_filter = [
        NewOrderProcessedFilter,
        SingleDateFilter,
    ]
    search_fields = ["order_number", "recipient_last_name"]
    empty_value_display = " - "

    class Media:
        js = [
            "admin/js/calendar.js",
            "admin/js/SelectBox.js",
            "js/FilterDateTimeShortcuts.js",
        ]
        css = {
            "all": ["css/new_order_admin_hide_columns.css"],
        }

    def action(self, obj):
        classes = ["button"]
        target = "_blank"
        popup = False
        if popup:
            classes.append("related-widget-wrapper-link")

        if getattr(obj, "id", None):
            text = "Update"
            url = (
                f'{reverse(f"admin:{self.model._meta.app_label}_{self.model._meta.model_name}_change", args=(obj.id, ))}'
                f'{"?_popup=1" if popup else ""}'
            )
        else:
            text = "Save As"
            params = {"order_number": obj.order_number}
            if popup:
                params["popup"] = 1
            if obj.delivery_shift_id:
                params["delivery_shift"] = obj.delivery_shift_id
            if obj.online_id:
                params["online_id"] = obj.online_id
            if obj.recipient_phone_number:
                params["recipient_phone_number"] = obj.recipient_phone_number
            url = f'{reverse(f"admin:{self.model._meta.app_label}_{self.model._meta.model_name}_add")}?{urlencode(params)}'

        return mark_safe(
            "<a "
            f'class="{" ".join(classes)}" '
            f'data-href-template="{url}"'
            'style="width: 50px;" '
            f'href="{url}" '
            f'target="{target}"'
            f">{text}</a>"
        )


@login_required
def NewOrderView(request):
    model_admin = NewOrderAdmin(Delivery, admin_site)

    FormSet = model_admin.get_changelist_formset(request)

    if request.method == "POST" and "_save" in request.POST:
        prefix = FormSet.get_default_prefix()
        num_forms = int(request.POST.get(f"{prefix}-TOTAL_FORMS", 0))
        objects: Dict[int, Dict[str, str]] = {i: {} for i in range(num_forms)}
        pk_pattern = re.compile(
            r"{}-(?P<num>\d+)-(?P<field>\w+)$".format(
                re.escape(FormSet.get_default_prefix())
            )
        )
        for key, value in request.POST.items():
            match = pk_pattern.match(key)
            if match:
                num = int(match["num"])
                field = match["field"]
                objects[num][field] = value

        existing_deliveries = Delivery.objects.in_bulk(
            list(filter(None, [o["id"] for o in objects.values()]))
        )

        for obj in objects.values():
            pk = obj["id"]
            order_number = obj["order_number"]
            if not obj["delivery_shift"] or not order_number:
                continue
            delivery_shift_id = obj["delivery_shift"]
            if pk:
                delivery = existing_deliveries[int(pk)]
                if (
                    delivery.order_number == order_number
                    and delivery.delivery_shift_id == delivery_shift_id
                ):
                    continue
                delivery.order_number = order_number
                delivery.delivery_shift_id = delivery_shift_id
            else:
                try:
                    # check to see if processed by the time the button was hit
                    Delivery.objects.get(order_number=order_number)
                    continue
                except Delivery.DoesNotExist:
                    pass
                recipient_phone_number = obj["recipient_phone_number"] or None
                online_id = obj["online_id"] or None
                delivery = Delivery(
                    order_number=order_number,
                    delivery_shift_id=delivery_shift_id,
                    recipient_phone_number=recipient_phone_number,
                    online_id=online_id,
                )
                delivery.save()
                delivery.sync()
            delivery.save()

    if "include_processed" not in request.GET:
        q = request.GET.copy()
        q["include_processed"] = "False"
        request.GET = q
        request.META["QUERY_STRING"] = request.GET.urlencode()
    if "date" not in request.GET:
        q = request.GET.copy()
        q["date"] = datetime.date.today().strftime("%Y-%m-%d")
        request.GET = q
        request.META["QUERY_STRING"] = request.GET.urlencode()

    cl = NewOrderChangeList(
        request,
        Delivery,
        model_admin.list_display,
        None,  # list_display_links
        model_admin.list_filter,  # list_filter
        None,  # date_hierarchy
        model_admin.search_fields,
        False,  # list_select_related
        100,  # list_per_page
        200,  # list_max_show_all
        model_admin.list_editable,
        model_admin,
        model_admin.sortable_by,
    )

    cl.formset = FormSet(  # pylint: disable=attribute-defined-outside-init
        data={
            "form-TOTAL_FORMS": len(cl.result_list),
            "form-INITIAL_FORMS": len(cl.result_list),
            **{
                f"form-{n}-id": getattr(o, "id", None)
                for n, o in enumerate(cl.result_list)
            },
            **{
                f"form-{n}-order_number": getattr(o, "order_number", None)
                for n, o in enumerate(cl.result_list)
            },
            **{
                f"form-{n}-delivery_shift": getattr(o, "delivery_shift_id", None)
                for n, o in enumerate(cl.result_list)
            },
            **{
                f"form-{n}-recipient_phone_number": getattr(
                    o, "recipient_phone_number", None
                )
                for n, o in enumerate(cl.result_list)
            },
            **{
                f"form-{n}-online_id": getattr(o, "online_id", None)
                for n, o in enumerate(cl.result_list)
            },
        },
        auto_id="order_number",
    )

    context = {
        **admin_site.each_context(request),
        "module_name": "Orders",
        "title": "New Orders",
        "is_popup": False,
        "to_field": cl.to_field,
        "cl": cl,
        "media": model_admin.media,
        "has_add_permission": False,
        "opts": cl.opts,
        "preserved_filters": model_admin.get_preserved_filters(request),
        "can_add_related": False,
    }

    request.current_app = "Orders"

    return TemplateResponse(request, "admin/change_list.html", context)
