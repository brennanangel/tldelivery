import datetime
from os import path
import requests
import phonenumbers
from django.db import models
from django.utils.safestring import mark_safe
from django.utils.html import format_html
from django.conf import settings
from django.urls import reverse

# Create your models here.

class Shift(models.Model):
    date = models.DateField()
    time = models.CharField(
        choices=(
            ('AM', 'AM'),
            ('PM', 'PM'),
            ('SP', 'Special')
        ),
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
    @property
    def date_display(self):
        return self.date.strftime('%m/%d (%a)')
    @property
    def datetime_display(self):
        return "{date} {time}".format(
            date=self.date_display,
            time=self.time
        )
    @property
    def slots_filled(self):
        return self.delivery_set.count()
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
        return self.date >= datetime.date.today() and self.slots_remaining > 0

    def push_button(self):
        if not self.id:
            return '[save record first]'
        return mark_safe(
            format_html(
                '<button class="btn btn-primary onfleet-button" name="_push" data-id="{id}">Send to Onfleet</button>',
                id=self.id,
                order_number=self.order_number
            )
        )
    push_button.short_description = 'Create task in OnFleet'
    push_button.allow_tags = True

    def shift_actions(self):
        return mark_safe(
            format_html(
                '<a class="btn" href="{walk}" target="_blank">Generate Walk List</a>&nbsp;'
                '<button class="btn onfleet-button shift" name="_push" data-id="{id}">Send to Onfleet</button>',
                walk=reverse('walk-list', args=[self.id]),
                id=self.id
            )
        )
    shift_actions.short_description = 'Shift Actions'
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
    )
    recipient_email = models.CharField(
        blank=True,
        null=True,
        max_length=255,
    )
    address_name = models.CharField(
        blank=True,
        null=True,
        max_length=255,
        help_text='e.g., Company Name'
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
    notes = models.TextField(
        blank=True,
        null=True
    )

    @property
    def recipient_sort_name(self):
        return self.recipient_last_name or 'zzUnknown'

    @property
    def recipient_name(self):
        if self.recipient_first_name is None:
            return self.recipient_last_name
        elif self.recipient_last_name is None:
            return self.recipient_first_name + ' [LAST NAME UNKNOWN]'
        return self.recipient_first_name + ' ' + self.recipient_last_name

    def sync(self):
        if not self.order_number:
            raise ValueError('Order number required to sync.')
        if not settings.CLOVER_API_KEY:
            raise ValueError('Environment CLOVER_API_KEY not set.')
        if not settings.CLOVER_MERCHANT_ID:
            raise ValueError('Environment CLOVER_MERCHANT_ID not set.')
        if not settings.CLOVER_INTEGRATION_API:
            raise ValueError('Environment CLOVER_INTEGRATION_API not set.')
        orders_url = path.join(
            settings.CLOVER_INTEGRATION_API,
            'merchants',
            settings.CLOVER_MERCHANT_ID,
            'orders')

        order_params = {'expand': 'lineItems,customers'}
        customer_params = {'expand': 'addresses,emailAddresses,phoneNumbers'}
        headers = {
            'Content-Type': 'Application/JSON',
            'Authorization': 'Bearer ' + settings.CLOVER_API_KEY
        }
        order_response = requests.get(
            path.join(orders_url, self.order_number.upper()),
            params=order_params,
            headers=headers
        )

        if order_response.status_code == 404:
            raise ValueError('Order {} not found in Clover.'.format(self.order_number))
        elif order_response.status_code != 200:
            order_response.raise_for_status()

        # save if not yet
        if not self.pk:
            self.save()

        order_data = order_response.json()

        # line items
        if order_data['lineItems'] and order_data['lineItems']['elements'] and len(order_data['lineItems']['elements']):
            items = order_data['lineItems']['elements']
            current_items = [i.clover_id for i in self.item_set.all()]
            for item in items:
                if item['refunded']:
                    continue
                cid = item['id']
                if cid in current_items:
                    continue
                item_name = item['name']
                if 'Shipping and Handling' in item_name or 'Delivery' in item_name:
                    continue
                self.item_set.create(
                    clover_id=cid,
                    item_name=item_name,
                    quantity=1,
                )

        # set customer information
        if not order_data.get('customers') or not order_data['customers']['elements']:
            return
        customers = order_data['customers']['elements']
        if len(customers) != 1:
            raise ValueError('Unexpected number ({}) of customers found on order'.format(len(customers)))
        customer = customers[0]
        self.recipient_last_name = customer['lastName']
        self.recipient_first_name = customer['firstName']
        if customer['href']:
            customer_response = requests.get(customer['href'], params=customer_params, headers=headers)
            if customer_response.status_code != 200:
                customer_response.raise_for_status()
            customer_data = customer_response.json()
            if customer_data['addresses'] and\
                    customer_data['addresses']['elements'] and\
                    len(customer_data['addresses']['elements']):
                try:
                    # first look for best address
                    address = next(a for a in customer_data['addresses']['elements'] if a['address1'])
                except StopIteration:
                    address = customer_data['addresses']['elements'][0]
                self.address_line_1 = address['address1']
                self.address_line_2 = address['address2']
                self.address_city = address['city']
                self.address_postal_code = address['zip']
            if customer_data['phoneNumbers'] and\
                    customer_data['phoneNumbers']['elements'] and\
                    len(customer_data['phoneNumbers']['elements']):
                try:
                    # first look for best address
                    phone_number = next(a for a in customer_data['phoneNumbers']['elements'] if a['phoneNumber'])
                except StopIteration:
                    phone_number = customer_data['phoneNumbers']['elements'][0]
                self.recipient_phone_number = phone_number['phoneNumber']
            if customer_data['emailAddresses'] and\
                    customer_data['emailAddresses']['elements'] and\
                    len(customer_data['emailAddresses']['elements']):
                try:
                    # first look for best address
                    email = next(a for a in customer_data['emailAddresses']['elements'] if a['emailAddress'])
                except StopIteration:
                    email = customer_data['emailAddresses']['elements'][0]
                self.recipient_email = email['emailAddress']

    def serialize_for_onfleet(self):
        notes = "Order Number: {}\nItems:".format(self.order_number)
        if self.item_set.count() < 1:
            notes += "\n    No Items Found"
        else:
            for item in self.item_set.all():
                notes += "\n - {item_display}{item_notes}".format(
                    item_display=item.display,
                    item_notes=' ({})'.format(item.note) if item.note else ''
                )
        if self.notes:
            notes += "\n\n{}".format(self.notes)
        return {
            'metadata': [{
                "name": "order_number",
                "type": "string",
                "value": self.order_number,
                "visibility": [
                    "api",
                    "dashboard",
                ]
            }] if self.order_number else None,
            'destination': {
                'address': {
                    'unparsed': ', '.join(filter(None, [
                        self.address_line_1,
                        self.address_line_2,
                        self.address_city,
                        'San Francisco',
                        'CA',
                        self.address_postal_code,
                    ])),
                },
                'notes': self.address_name,
            },
            'recipients': [{
                'name': self.recipient_name,
                'phone': phonenumbers.format_number(
                    phonenumbers.parse(self.recipient_phone_number, 'US'),
                    phonenumbers.PhoneNumberFormat.E164
                ) if self.recipient_phone_number else None
            }],
            'completeAfter': datetime.datetime.combine(
                datetime.date(2018, 10, 1),
                datetime.time(13 if self.delivery_shift.time == 'PM' else 9)
                ).timestamp() * 1000,
            'completeBefore': datetime.datetime.combine(
                self.delivery_shift.date,
                datetime.time(18 if self.delivery_shift.time == 'PM' else 12)
                ).timestamp() * 1000,
            'notes': notes,
            'quantity': 1,
            'serviceTime': 15
        }

    def sync_button(self):
        return mark_safe(
            format_html(
                '<button class="btn btn-primary sync-button" name="_sync" data-order-id="{order_number}">Sync with Clover</button>',
                order_number=self.order_number
            )
        )
    sync_button.short_description = 'Sync Order from Clover'
    sync_button.allow_tags = True

    def push_button(self):
        if not self.id:
            return '[save record first]'
        return mark_safe(
            format_html(
                '<button class="btn btn-primary onfleet-button order" name="_push" data-id="{id}">Send to Onfleet</button>',
                id=self.id,
                order_number=self.order_number
            )
        )
    push_button.short_description = 'Create task in OnFleet'
    push_button.allow_tags = True

    def generate_delivery_sheet(self):
        if not self.id:
            return '[save record first]'
        return mark_safe(
            format_html(
                '<a class="btn" href="{order_sheet}" target="_blank">Generate Delivery Sheet</a>&nbsp;',
                order_sheet=reverse('order-sheet', args=[self.id]),
            )
        )
    generate_delivery_sheet.short_description = 'Generate delivery sheet'
    generate_delivery_sheet.allow_tags = True

    def __str__(self):
        return "{name} ({order_number})".format(
            name=self.recipient_name,
            order_number=self.order_number,
        )

    class Meta:
        verbose_name_plural = 'Deliveries'


class Item(models.Model):
    Delivery = models.ForeignKey(
        Delivery,
        db_index=True,
        on_delete=models.CASCADE,
    )
    item_name = models.CharField(
        max_length=255,
    )
    quantity = models.SmallIntegerField()
    picked_up = models.BooleanField(
        default=False
    )
    note = models.CharField(
        null=True,
        blank=True,
        max_length=255
    )
    clover_id = models.CharField(
        null=True,
        blank=True,
        max_length=40,
    )

    @property
    def display(self):
        ret = ''
        if self.picked_up:
            ret += '[ALREADY PICKED UP] '
        ret += self.item_name
        if self.quantity != 1:
            ret += ' - {}'.format(self.quantity)
        return ret
