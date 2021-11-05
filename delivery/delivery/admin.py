import datetime
import csv
from typing import List
from django.contrib import admin, messages
from django.urls import reverse

from django.core.cache import cache
from django.http import HttpResponseRedirect, HttpResponse
from django.contrib.admin.templatetags.admin_urls import add_preserved_filters
from django.forms import ModelForm
from django.contrib.admin.utils import quote
from django.db.models import Count

from .models import (
    Shift,
    Delivery,
    Item,
)
from .actions import create_onfleet_task_from_order


def export_as_csv(self, request, queryset) -> HttpResponse:
    meta = self.model._meta
    field_names = [field.name for field in meta.fields]

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = "attachment; filename={}.csv".format(meta)
    writer = csv.writer(response)

    writer.writerow(field_names)
    for obj in queryset:
        writer.writerow([getattr(obj, field) for field in field_names])

    return response


export_as_csv.short_description = "Export Selected"  # type: ignore


class IsAvailableFilter(admin.SimpleListFilter):
    title = "Is Future"
    parameter_name = "is_future"

    def lookups(self, request, model_admin):
        return (("Yes", "Yes"), ("All", "All"))

    def queryset(self, request, queryset):
        value = self.value()
        if value == "Yes":
            return queryset.filter(date__gte=datetime.date.today())

        return queryset


class ItemInline(admin.TabularInline):
    model = Item
    extra = 0


class DeliveryInline(admin.TabularInline):
    model = Delivery
    fields = ("order_number", "recipient_name", "recipient_phone_number")
    readonly_fields = ("recipient_name", "recipient_phone_number")
    show_change_link = True
    extra = 0

    def get_max_num(self, request, obj=None, **kwargs):
        return (obj and obj.slots_available) or 20


class ShiftAdmin(admin.ModelAdmin):
    readonly_fields = (
        "available",
        "shift_actions",
    )
    list_display = ("shift", "available", "slots", "comment", "shift_actions")
    list_filter = (IsAvailableFilter,)
    ordering = (
        "date",
        "time",
    )
    actions = [export_as_csv]

    inlines = [DeliveryInline]

    def shift(self, obj):
        return obj.datetime_display

    def slots(self, obj):
        return obj.slots_display

    def get_queryset(self, request):

        shift_counts = Delivery.objects.values("delivery_shift_id").annotate(
            Count("delivery_shift_id")
        )
        for shift_count in shift_counts:
            cache.set(
                Shift.FILLED_CACHE_TEMPLATE.format(id=shift_count["delivery_shift_id"]),
                shift_count["delivery_shift_id__count"],
            )

        return super().get_queryset(request)


class DeliveryForm(ModelForm):
    class Meta:
        model = Delivery
        exclude: List[str] = []

    def __init__(self, *args, **kwargs):
        super(DeliveryForm, self).__init__(*args, **kwargs)
        qs = Shift.objects.filter(date__gte=datetime.date.today())
        if "instance" in kwargs and getattr(
            kwargs["instance"], "delivery_shift_id", None
        ):
            qs = qs.union(Shift.objects.filter(pk=kwargs["instance"].delivery_shift_id))

        self.fields["delivery_shift"].queryset = qs.order_by("date", "time")


class DeliveryAdmin(admin.ModelAdmin):
    form = DeliveryForm
    list_display = (
        "order_number",
        "delivery_shift",
        "recipient_name",
        "recipient_phone_number",
        "generate_delivery_sheet",
        "push_button",
    )
    list_filter = ("delivery_shift",)
    search_fields = [
        "order_number",
        "recipient_last_name",
        "recipient_phone_number",
        "recipient_first_name",
    ]
    readonly_fields = (
        "sync_button",
        "generate_delivery_sheet",
        "push_button",
    )
    list_editable = ("delivery_shift",)
    fieldsets = (
        ("Main", {"fields": ("order_number", "delivery_shift")}),
        (
            "Actions",
            {"fields": ("sync_button", "generate_delivery_sheet", "push_button")},
        ),
        (
            "Recipient",
            {
                "fields": (
                    "recipient_last_name",
                    "recipient_first_name",
                    "recipient_phone_number",
                    "recipient_email",
                )
            },
        ),
        (
            "Address",
            {
                "fields": (
                    "address_name",
                    "address_line_1",
                    "address_line_2",
                    "address_city",
                    "address_postal_code",
                )
            },
        ),
        ("Other", {"fields": ("notes",)}),
    )
    actions = [export_as_csv]
    inlines = [ItemInline]

    def response_change(self, request, obj):
        if "_sync" in request.POST:
            preserved_filters = self.get_preserved_filters(request)
            msg = "Order synced successfully."
            self.message_user(request, msg, messages.SUCCESS)
            redirect_url = request.path
            redirect_url = add_preserved_filters(
                {"preserved_filters": preserved_filters, "opts": obj._meta},
                redirect_url,
                popup=("_popup" in request.POST),
            )
            return HttpResponseRedirect(redirect_url)
        return super().response_change(request, obj)

    def response_add(self, request, obj, post_url_continue=None):
        if "_sync" in request.POST:
            opts = obj._meta
            preserved_filters = self.get_preserved_filters(request)
            msg = "Order synced successfully."
            self.message_user(request, msg, messages.SUCCESS)
            redirect_url = post_url_continue or reverse(
                "admin:%s_%s_change" % (opts.app_label, opts.model_name),
                args=(quote(obj.pk),),
                current_app=self.admin_site.name,
            )
            redirect_url = add_preserved_filters(
                {"preserved_filters": preserved_filters, "opts": obj._meta},
                redirect_url,
            )
            return HttpResponseRedirect(redirect_url)
        return super().response_add(request, obj)

    def save_model(self, request, obj, form, change):
        if "_sync" in request.POST:
            obj.sync()
        super().save_model(request, obj, form, change)
        if "_push" in request.POST:
            create_onfleet_task_from_order(obj)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        if "_sync" in request.POST or "_push" in request.POST:
            try:
                return super().change_view(request, object_id, form_url, extra_context)
            except Exception as exc:
                msg = "SYNC FAILED: " + str(exc)
                self.message_user(request, msg, messages.ERROR)
                preserved_filters = self.get_preserved_filters(request)
                redirect_url = request.path
                redirect_url = add_preserved_filters(
                    {"preserved_filters": preserved_filters}, redirect_url
                )
                return HttpResponseRedirect(redirect_url)
        return super().change_view(request, object_id, form_url, extra_context)

    def add_view(self, request, form_url="", extra_context=None):
        if "_sync" in request.POST:
            try:
                return super().add_view(request, form_url, extra_context)
            except Exception as exc:
                msg = "SYNC FAILED: " + str(exc)
                self.message_user(request, msg, messages.ERROR)
                preserved_filters = self.get_preserved_filters(request)
                redirect_url = request.path
                redirect_url = add_preserved_filters(
                    {"preserved_filters": preserved_filters}, redirect_url
                )
                return HttpResponseRedirect(redirect_url)
        return super().add_view(request, form_url, extra_context)

    def get_queryset(self, request):
        shift_counts = Delivery.objects.values("delivery_shift_id").annotate(
            Count("delivery_shift_id")
        )
        for shift_count in shift_counts:
            cache.set(
                Shift.FILLED_CACHE_TEMPLATE.format(id=shift_count["delivery_shift_id"]),
                shift_count["delivery_shift_id__count"],
            )

        return super().get_queryset(request)

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name == "delivery_shift":
            # dirty trick so queryset is evaluated and cached in .choices
            formfield.choices = formfield.choices
        return formfield


admin.site.register(Shift, ShiftAdmin)
admin.site.register(Delivery, DeliveryAdmin)
