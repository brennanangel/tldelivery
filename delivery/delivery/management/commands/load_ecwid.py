import csv
from datetime import datetime
from django.core.management.base import BaseCommand
from delivery.delivery.models import Shift, Delivery, Item
import phonenumbers

class Command(BaseCommand):
    help = 'Creates shifts as a template'

    def add_arguments(self, parser):
        parser.add_argument('file', type=str)

    def flush_order(self, order, items):
        if not hasattr(order, 'delivery_shift'):
            self.stdout.write(self.style.WARNING(f'Unable to determine shift for order {order}'))
            return
        if not items:
            self.stdout.write(self.style.WARNING(f'No items found for order {order}'))
            return
        try:
            order.save()
            for item in items:
                item.delivery_id = order.id
            Item.objects.filter(delivery_id=order.id).delete()
            Item.objects.bulk_create(items)
            if self.verbose:
                self.stdout.write(f'Saved order {order}')
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'Unable to save order {order}: {e}'))

    def handle(self, *args, **options):
        orders_file_path = options['file']
        shifts = list(Shift.objects.all())
        orders = list(Delivery.objects.all())
        self.verbose = True
        self.overwrite = True
        try:
            with open(orders_file_path) as f:
                reader = csv.DictReader(f, delimiter='\t')
                last_row = None
                order = None
                existing = False
                items = None

                for row in reader:
                    order_number = row['order_number']
                    if order_number != last_row:
                        if order is not None and not existing or self.overwrite:
                            self.flush_order(order, items)

                        # check if we've seen this before
                        last_row = order_number

                        try:
                            order = next(o for o in orders if o.order_number == order_number)
                            existing = True
                            if not self.overwrite:
                                if self.verbose:
                                    self.stdout.write(f'Skipping existing order {order}')
                                continue
                        except StopIteration:
                            existing = False
                            order = Delivery()

                        # build new order
                        order.recipient_email = row['email']
                        recipient_name = row['shipto_person_name'].split(' ')
                        if len(recipient_name) == 2:
                            order.recipient_first_name = recipient_name[0]
                            order.recipient_last_name = recipient_name[1]
                        else:
                            order.recipient_last_name = ' '.join(recipient_name)
                        try:
                            recipient_phone_number = phonenumbers.format_number(
                                phonenumbers.parse(row['shipto_person_phone'], 'US'),
                                phonenumbers.PhoneNumberFormat.E164
                            )
                        except Exception as e:
                            recipient_phone_number = None
                            self.stdout.write(self.style.WARNING(f'Unable to parse phone number for {order_number}: {e}'))
                        order.recipient_phone_number = recipient_phone_number
                        order.address_line_1 = row['shipto_person_street_1']
                        order.address_line_2 = row['shipto_person_street_2']
                        order.address_city = row['shipto_person_city']
                        order.address_postal_code = row['shipto_person_postal_code']
                        order.notes = row['order_comments']
                        order.order_number = row['order_number']
                        items = []
                    else:
                        if existing and not self.overwrite:
                            continue

                    item = Item()
                    item_name = row['name']
                    if 'Delivery' in item_name:
                        delivery = item_name.split(' ')
                        date = datetime.strptime(delivery[0], "%m/%d").date()
                        date = date.replace(year=2019)
                        if delivery[1] not in date.strftime('%A'):
                            self.stdout.write(self.style.WARNING(f'Invalid delivery shift {item_name}'))
                            continue
                        time = delivery[2]
                        shift = next(s for s in shifts if s.date == date and s.time == time)
                        order.delivery_shift = shift
                        continue
                    if 'shift' in item_name or 'shfft' in item_name:
                        delivery = item_name.split(' ')
                        date = datetime.strptime(delivery[1], "%m/%d/%Y").date()
                        if delivery[0] not in date.strftime('%A'):
                            self.stdout.write(self.style.WARNING(f'Invalid delivery shift {item_name}'))
                            continue
                        time = delivery[2]
                        shift = next(s for s in shifts if s.date == date and s.time == time)
                        order.delivery_shift = shift
                        continue
                    item.item_name = item_name
                    item.quantity = row['quantity']
                    item.note = 'ECWID order ' + row['order_number']
                    items.append(item)

                if not existing or self.overwrite:
                    self.flush_order(order, items)

        except FileNotFoundError:
            self.stdout.write(self.style.ERROR('File does not exist'))
            return
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error processing file: {e}'))
            if self.verbose:
                import traceback
                traceback.print_exc()
        self.stdout.write(self.style.SUCCESS('Done'))
