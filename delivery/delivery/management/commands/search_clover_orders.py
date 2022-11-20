import datetime

from django.core.management.base import BaseCommand

from delivery.delivery.actions import search_clover_orders


class Command(BaseCommand):
    help = "Search Clover for today's delivery orders"

    def add_arguments(self, parser):
        parser.add_argument("--date", nargs="?")
        parser.add_argument("--include-processed", action="store_true")

    def handle(self, *args, **options):
        if options["date"]:
            date = datetime.datetime.strptime(options["date"], "%Y-%m-%d").date()
        else:
            date = datetime.date.today()

        orders = search_clover_orders(
            date, include_processed=options["include_processed"]
        )
        if not orders:
            self.stdout.write(self.style.WARNING("No orders found"))
            return
        for o in orders:
            print(o)
