import os
import datetime
import pytz
from typing import Optional, Dict
import phonenumbers
from django.db import models
from django.conf import settings
from django.core.cache import cache
from django.utils.safestring import mark_safe
from django.utils.html import format_html
from django.urls import reverse
from delivery.delivery.clover import (
    request_clover_orders,
    request_clover_customer,
    is_clover_delivery_item,
)
from django.template.defaultfilters import truncatechars  # or truncatewords
from delivery.delivery.constants import DeliveryTypes


class Shift(models.Model):
    SHIFT_FILLED_CACHE_TEMPLATE = "shift_{id}_count_filled"
    date = models.DateField()
    time = models.CharField(
        choices=(("AM", "AM"), ("PM", "PM"), ("SP", "Special")),
        max_length=2,
    )
    slots_available = models.SmallIntegerField(
        default=20,
    )
    comment = models.CharField(
        blank=True,
        null=True,
        max_length=255,
    )
    notes = models.TextField(
        blank=True,
        null=True,
    )

    @classmethod
    def bust_available_shift_cache(cls) -> None:
        # naive bust for when we have changes
        cache.delete_many(
            [
                Shift.SHIFT_FILLED_CACHE_TEMPLATE.format(id=sid)
                for sid in cls.objects.all().values_list("id", flat=True)
            ]
        )

    @classmethod
    def set_available_shift_cache(cls) -> None:
        shift_ids = cls.objects.all().values_list("id", flat=True)
        shift_counts = Delivery.objects.values("delivery_shift_id").annotate(
            models.Count("delivery_shift_id")
        )
        count_by_shift = {
            shift_count["delivery_shift_id"]: shift_count["delivery_shift_id__count"]
            for shift_count in shift_counts
        }

        cache.set_many(
            {
                Shift.SHIFT_FILLED_CACHE_TEMPLATE.format(id=sid): count_by_shift.get(
                    sid, 0
                )
                for sid in shift_ids
            }
        )

    @property
    def date_display(self):
        return self.date.strftime("%m/%d (%a)")

    @property
    def datetime_display(self):
        return "{date} {time}".format(date=self.date_display, time=self.time)

    @property
    def slots_filled(self) -> int:
        if self.id is None:
            return 0
        cache_key = self.SHIFT_FILLED_CACHE_TEMPLATE.format(id=self.id)
        count = cache.get(cache_key, None)
        if count is None:
            self.set_available_shift_cache()
            count = cache.get(cache_key, 0)
        return count

    @property
    def slots_remaining(self):
        return self.slots_available - self.slots_filled

    @property
    def slots_display(self):
        return "{num} remaining ({filled}/{available})".format(
            num=self.slots_remaining,
            filled=self.slots_filled,
            available=self.slots_available,
        )

    @property
    def available(self):
        if self.date is None:
            return None
        return self.date >= datetime.date.today() and self.slots_remaining > 0

    def push_button(self):
        if not self.id:
            return "[save record first]"
        return mark_safe(
            format_html(
                '<button class="button button-primary onfleet-button" name="_push" data-id="{id}">Send to Onfleet</button>',
                id=self.id,
            )
        )

    push_button.short_description = "Create task in OnFleet"
    push_button.allow_tags = True

    def shift_actions(self):
        if self.id is None:
            return None
        return mark_safe(
            format_html(
                '<a class="button" href="{walk}" target="_blank">Generate Walk List</a>&nbsp;'
                '<button class="button onfleet-button shift" name="_push" data-id="{id}">Send to Onfleet</button>',
                walk=reverse("walk-list", args=[self.id]),
                id=self.id,
            )
        )

    shift_actions.short_description = "Shift Actions"
    shift_actions.allow_tags = True

    def __str__(self):
        return "{datetime} - {status}".format(
            datetime=self.datetime_display,
            status=self.slots_display,
        )

    class Meta:
        unique_together = (("date", "time"),)


class Delivery(models.Model):
    order_number = models.CharField(
        blank=True,
        null=True,
        max_length=20,
        unique=True,
    )
    delivery_shift = models.ForeignKey(
        Shift,
        db_index=True,
        on_delete=models.PROTECT,
    )
    recipient_last_name = models.CharField(
        blank=True,
        null=True,
        max_length=40,
    )
    recipient_first_name = models.CharField(
        blank=True,
        null=True,
        max_length=40,
    )
    recipient_phone_number = models.CharField(
        blank=True,
        null=True,
        max_length=255,
        unique=True,
    )
    recipient_email = models.CharField(
        blank=True,
        null=True,
        max_length=255,
    )
    address_name = models.CharField(
        blank=True, null=True, max_length=255, help_text="e.g., Company Name"
    )
    address_line_1 = models.CharField(
        blank=True,
        null=True,
        max_length=255,
    )
    address_line_2 = models.CharField(
        blank=True,
        null=True,
        max_length=255,
    )
    address_city = models.CharField(
        blank=True,
        null=True,
        max_length=40,
    )
    address_postal_code = models.CharField(
        blank=True,
        null=True,
        max_length=10,
    )
    notes = models.TextField(blank=True, null=True)
    online_id = models.CharField(blank=True, null=True, max_length=20)
    delivery_type = models.IntegerField(
        choices=(
            (DeliveryTypes.WHITE_GLOVE, "White Glove"),
            (DeliveryTypes.CURBSIDE, "Curbside"),
        ),
        default=DeliveryTypes.WHITE_GLOVE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def recipient_sort_name(self):
        return self.recipient_last_name or "zzUnknown"

    @property
    def recipient_name(self):
        if self.recipient_first_name is None:
            if self.recipient_last_name is None:
                return "[No Name]"
            return self.recipient_last_name
        elif self.recipient_last_name is None:
            return self.recipient_first_name + " [LAST NAME UNKNOWN]"
        return self.recipient_first_name + " " + self.recipient_last_name

    @property
    def recipient_phone_number_formatted(self):
        if not self.recipient_phone_number:
            return None
        return phonenumbers.format_number(
            phonenumbers.parse(self.recipient_phone_number, "US"),
            phonenumbers.PhoneNumberFormat.E164,
        )

    def short_notes(self) -> Optional[str]:
        if not self.notes:
            return None
        return truncatechars(self.notes, 50)

    short_notes.description = "Notes"

    def online_order_link(self):
        if self.online_id is None:
            return None
        return mark_safe(
            format_html(
                '<a href="{base}/{online_id}" target="_blank">view</a>',
                base=os.path.join(settings.SHOPIFY_APP_URL, "admin", "orders"),
                online_id=self.online_id,
            )
        )

    online_order_link.short_description = "Shopify Order"

    def _load_clover_items(self, order_data):
        if not order_data.get("lineItems", None):
            return
        if not order_data["lineItems"].get("elements", None):
            return
        items = order_data["lineItems"]["elements"]
        current_items = [i.item_name for i in self.item_set.all()]
        item_dict: Dict[str, int] = {}
        for item in items:
            if item["refunded"]:
                continue
            item_name = item["name"]
            if item_name in current_items:
                continue
            if is_clover_delivery_item(item_name):
                continue
            item_dict[item_name] = item_dict.get(item_name, 0) + 1
        for item in items:
            item_name = item["name"]
            quantity = item_dict.pop(item_name, 0)
            if quantity <= 0:
                continue
            self.item_set.create(
                clover_id=item["id"],
                item_name=item_name,
                quantity=quantity,
                is_pulled=True,
            )

    def _load_clover_customer(self, order_data):
        if not order_data.get("customers", None) or not order_data["customers"].get(
            "elements", None
        ):
            return
        customers = order_data["customers"]["elements"]
        if len(customers) != 1:
            raise ValueError(
                f"Unexpected number ({len(customers)}) of customers found on order"
            )
        customer = customers[0]
        self.recipient_last_name = customer.get("lastName")
        self.recipient_first_name = customer.get("firstName")
        # get customer data from Clover
        if customer["href"]:
            customer_data = request_clover_customer(customer["id"])
            self.recipient_last_name = self.recipient_last_name or customer_data.get(
                "lastName", None
            )
            self.recipient_first_name = self.recipient_first_name or customer_data.get(
                "firstName", None
            )
            #
            # get address data
            if customer_data["addresses"] and customer_data["addresses"]["elements"]:
                try:
                    # first look for best address
                    address = next(
                        a
                        for a in customer_data["addresses"]["elements"]
                        if a["address1"]
                    )
                except StopIteration:
                    address = customer_data["addresses"]["elements"][0]
                self.address_line_1 = address.get("address1")
                self.address_line_2 = address.get("address2")
                self.address_city = address["city"]
                self.address_postal_code = address["zip"]
            #
            # get phone numbers
            if (
                self.recipient_phone_number is None
                and customer_data["phoneNumbers"]
                and customer_data["phoneNumbers"]["elements"]
            ):
                try:
                    # first look for best address
                    phone_number = next(
                        a
                        for a in customer_data["phoneNumbers"]["elements"]
                        if a["phoneNumber"]
                    )
                except StopIteration:
                    phone_number = customer_data["phoneNumbers"]["elements"][0]
                self.recipient_phone_number = phone_number["phoneNumber"]
            # get email address
            if (
                customer_data["emailAddresses"]
                and customer_data["emailAddresses"]["elements"]
            ):
                try:
                    # first look for best address
                    email = next(
                        a
                        for a in customer_data["emailAddresses"]["elements"]
                        if a["emailAddress"]
                    )
                except StopIteration:
                    email = customer_data["emailAddresses"]["elements"][0]
                self.recipient_email = email["emailAddress"]

    def load_from_clover(self, order_data, skip_items=False):
        if not self.notes:
            self.notes = order_data.get("note", self.notes)
        clover_created_time = order_data.get("createdTime", None)
        self.created_at = (
            datetime.datetime.fromtimestamp(clover_created_time / 1000, tz=pytz.UTC)
            if clover_created_time
            else None
        )
        if not skip_items:
            self._load_clover_items(order_data)
        self._load_clover_customer(order_data)

    @classmethod
    def create_from_clover(
        cls, order_data, delivery_shift: Optional[Shift] = None, skip_items=False
    ):
        order_number = order_data["id"]
        if not order_number:
            raise ValueError("No order number found in payload")
        d = cls(order_number=order_number, delivery_shift=delivery_shift)
        d.load_from_clover(order_data, skip_items=skip_items)
        return d

    def sync(self):
        if not self.order_number:
            raise ValueError("Order number required to sync.")

        order_data = request_clover_orders(order_number=self.order_number)

        # save if not yet
        if not self.pk:
            self.save()

        self.load_from_clover(order_data)

    def serialize_for_onfleet(self):
        notes = "Order Number: {}\nItems:".format(self.order_number)
        if self.item_set.count() < 1:
            notes += "\n    No Items Found"
        else:
            for item in self.item_set.all():
                notes += "\n - {item_display}{item_notes}".format(
                    item_display=item.display,
                    item_notes=" ({})".format(item.note) if item.note else "",
                )
        if self.notes:
            notes += "\n\n{}".format(self.notes)
        return {
            "metadata": [
                {
                    "name": "order_number",
                    "type": "string",
                    "value": self.order_number,
                    "visibility": [
                        "api",
                        "dashboard",
                    ],
                }
            ]
            if self.order_number
            else None,
            "destination": {
                "address": {
                    "unparsed": ", ".join(
                        filter(
                            None,
                            [
                                self.address_line_1,
                                self.address_line_2,
                                self.address_city,
                                "San Francisco",
                                "CA",
                                self.address_postal_code,
                            ],
                        )
                    ),
                },
                "notes": self.address_name,
            },
            "recipients": [
                {
                    "name": self.recipient_name,
                    "phone": self.recipient_phone_number_formatted,
                }
            ],
            "completeAfter": datetime.datetime.combine(
                min(self.delivery_shift.date, datetime.date.today()),
                datetime.time(
                    13 if self.delivery_shift.time == "PM" else 9,
                    tzinfo=pytz.timezone("America/Los_Angeles"),
                ),
            ).timestamp()
            * 1000,
            "completeBefore": datetime.datetime.combine(
                self.delivery_shift.date,
                datetime.time(
                    18 if self.delivery_shift.time == "PM" else 12,
                    tzinfo=pytz.timezone("America/Los_Angeles"),
                ),
            ).timestamp()
            * 1000,
            "notes": notes,
            "quantity": 1,
            "serviceTime": 15,
        }

    def sync_button(self):
        return mark_safe(
            format_html(
                '<button class="button button-primary sync-button" name="_sync" data-order-id="{order_number}">Sync with Clover</button>',
                order_number=self.order_number,
            )
        )

    sync_button.short_description = "Sync Order from Clover"
    sync_button.allow_tags = True

    def push_button(self):
        if not self.id:
            return "[save record first]"
        return mark_safe(
            format_html(
                '<button class="button button-primary onfleet-button order" name="_push" data-id="{id}">Send to Onfleet</button>',
                id=self.id,
                order_number=self.order_number,
            )
        )

    push_button.short_description = "Create task in OnFleet"
    push_button.allow_tags = True

    def generate_delivery_sheet(self):
        if not self.id:
            return "[save record first]"
        return mark_safe(
            format_html(
                '<a class="button" href="{order_sheet}" target="_blank">Generate Delivery Sheet</a>&nbsp;',
                order_sheet=reverse("order-sheet", args=[self.id]),
            )
        )

    generate_delivery_sheet.short_description = "Generate delivery sheet"
    generate_delivery_sheet.allow_tags = True

    def __str__(self):
        return "{name} ({order_number})".format(
            name=self.recipient_name,
            order_number=self.order_number,
        )

    class Meta:
        verbose_name_plural = "Deliveries"


class Item(models.Model):
    delivery = models.ForeignKey(
        Delivery,
        db_index=True,
        on_delete=models.CASCADE,
    )
    item_name = models.CharField(
        max_length=255,
    )
    quantity = models.SmallIntegerField()
    picked_up = models.BooleanField(default=False)
    note = models.CharField(null=True, blank=True, max_length=255)
    clover_id = models.CharField(
        null=True,
        blank=True,
        max_length=40,
    )
    is_pulled = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.item_name} ({self.quantity})"

    @property
    def display(self):
        ret = ""
        if self.picked_up:
            ret += "[ALREADY PICKED UP] "
        ret += self.item_name
        if self.quantity != 1:
            ret += " - {}".format(self.quantity)
        return ret
